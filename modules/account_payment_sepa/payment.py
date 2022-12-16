#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime
import os
from itertools import groupby

import genshi
import genshi.template
from sql import Literal

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from trytond.tools import reduce_ids

__metaclass__ = PoolMeta
__all__ = ['Journal', 'Group', 'Payment', 'Mandate']


class Journal:
    __name__ = 'account.payment.journal'
    company_party = fields.Function(fields.Many2One('party.party',
            'Company Party'), 'on_change_with_company_party')
    sepa_bank_account_number = fields.Many2One('bank.account.number',
        'Bank Account Number', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        domain=[
            ('type', '=', 'iban'),
            ('account.owners', '=', Eval('company_party')),
            ],
        depends=['process_method', 'company_party'])
    sepa_payable_flavor = fields.Selection([
            (None, ''),
            ('pain.001.001.03', 'pain.001.001.03'),
            ('pain.001.001.05', 'pain.001.001.05'),
            ], 'Payable Flavor', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        depends=['process_method'])
    sepa_receivable_flavor = fields.Selection([
            (None, ''),
            ('pain.008.001.02', 'pain.008.001.02'),
            ('pain.008.001.04', 'pain.008.001.04'),
            ], 'Receivable Flavor', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        depends=['process_method'])
    sepa_batch_booking = fields.Boolean('Batch Booking', states={
            'invisible': Eval('process_method') != 'sepa',
            },
        depends=['process_method'])
    sepa_charge_bearer = fields.Selection([
            ('DEBT', 'Debtor'),
            ('CRED', 'Creditor'),
            ('SHAR', 'Shared'),
            ('SLEV', 'Service Level'),
            ], 'Charge Bearer', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        depends=['process_method'])

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        sepa_method = ('sepa', 'SEPA')
        if sepa_method not in cls.process_method.selection:
            cls.process_method.selection.append(sepa_method)

    @classmethod
    def default_company_party(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            return Company(company_id).party.id

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        if self.company:
            return self.company.party.id

    @staticmethod
    def default_sepa_charge_bearer():
        return 'SLEV'


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


class Group:
    __name__ = 'account.payment.group'
    sepa_message = fields.Text('SEPA Message', readonly=True, states={
            'invisible': ~Eval('sepa_message'),
            })
    sepa_filename = fields.Function(fields.Char('SEPA Filename'),
        'get_sepa_filename')

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._error_messages.update({
                'no_mandate': 'No valid mandate for payment "%s"',
                })

    def get_sepa_filename(self, name):
        return self.rec_name + '.xml'

    def get_sepa_template(self):
        if self.kind == 'payable':
            return loader.load('%s.xml' % self.journal.sepa_payable_flavor)
        elif self.kind == 'receivable':
            return loader.load('%s.xml' % self.journal.sepa_receivable_flavor)

    def process_sepa(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        if self.kind == 'receivable':
            payments = [p for p in self.payments if not p.sepa_mandate]
            mandates = Payment.get_sepa_mandates(payments)
            for payment, mandate in zip(payments, mandates):
                if not mandate:
                    self.raise_user_error('no_mandate', payment.rec_name)
                Payment.write([payment], {
                        'sepa_mandate': mandate,
                        })
        tmpl = self.get_sepa_template()
        if not tmpl:
            raise NotImplementedError
        self.sepa_message = tmpl.generate(group=self,
            datetime=datetime).filter(remove_comment).render()

    @property
    def sepa_initiating_party(self):
        return self.company.party

    def sepa_group_payment_key(self, payment):
        key = (('date', payment.date),)
        if self.kind == 'receivable':
            key += (('sequence_type', payment.sepa_mandate.sequence_type),)
        return key

    def sepa_group_payment_id(self, key):
        payment_id = str(key['date'].toordinal())
        if self.kind == 'receivable':
            payment_id += '-' + key['sequence_type']
        return payment_id

    @property
    def sepa_payments(self):
        keyfunc = self.sepa_group_payment_key
        payments = sorted(self.payments, key=keyfunc)
        for key, grouped_payments in groupby(payments, key=keyfunc):
            yield dict(key), list(grouped_payments)


class Payment:
    __name__ = 'account.payment'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate', 'Mandate',
        ondelete='RESTRICT',
        domain=[
            ('party', '=', Eval('party', -1)),
            ],
        depends=['party'])

    @classmethod
    def get_sepa_mandates(cls, payments):
        mandates = []
        for payment in payments:
            for mandate in payment.party.sepa_mandates:
                if mandate.is_valid:
                    break
            else:
                mandate = None
            mandates.append(mandate)
        return mandates

    @property
    def sepa_end_to_end_id(self):
        return str(self.id)

    sepa_instruction_id = sepa_end_to_end_id

    @property
    def sepa_remittance_information(self):
        if self.description:
            return self.description
        elif self.line and self.line.origin:
            return self.line.origin.rec_name

    @property
    def sepa_bank_account_number(self):
        if self.kind == 'receivable':
            if self.sepa_mandate:
                return self.sepa_mandate.account_number
        else:
            for account in self.party.bank_accounts:
                for number in account.numbers:
                    if number.type == 'iban':
                        return number


class Mandate(Workflow, ModelSQL, ModelView):
    'SEPA Mandate'
    __name__ = 'account.payment.sepa.mandate'
    party = fields.Many2One('party.party', 'Party', required=True, select=True,
        states={
            'readonly': Eval('state').in_(
                ['requested', 'validated', 'canceled']),
            },
        depends=['state'])
    account_number = fields.Many2One('bank.account.number', 'Account Number',
        states={
            'readonly': Eval('state').in_(['validated', 'canceled']),
            'required': Eval('state') == 'validated',
            },
        domain=[
            ('type', '=', 'iban'),
            ('account.owners', '=', Eval('party')),
            ],
        depends=['state', 'party'])
    identification = fields.Char('Identification', size=35,
        states={
            'readonly': Eval('state').in_(['validated', 'canceled']),
            'required': Eval('state') == 'validated',
            },
        depends=['state'])
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ],
        states={
            'readonly': Eval('state') != 'draft',
            },
        depends=['state'])
    type = fields.Selection([
            ('recurrent', 'Recurrent'),
            ('one-off', 'One-off'),
            ], 'Type',
        states={
            'readonly': Eval('state').in_(['validated', 'canceled']),
            },
        depends=['state'])
    signature_date = fields.Date('Signature Date',
        states={
            'readonly': Eval('state').in_(['validated', 'canceled']),
            'required': Eval('state') == 'validated',
            },
        depends=['state'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('requested', 'Requested'),
            ('validated', 'Validated'),
            ('canceled', 'Canceled'),
            ], 'State', readonly=True)
    payments = fields.One2Many('account.payment', 'sepa_mandate', 'Payments')
    has_payments = fields.Function(fields.Boolean('Has Payments'),
        'has_payments')

    @classmethod
    def __setup__(cls):
        super(Mandate, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'requested'),
                ('requested', 'validated'),
                ('validated', 'canceled'),
                ('requested', 'canceled'),
                ('requested', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(
                        ['requested', 'validated']),
                    },
                'draft': {
                    'invisible': Eval('state') != 'requested',
                    },
                'request': {
                    'invisible': Eval('state') != 'draft',
                    },
                'validate_mandate': {
                    'invisible': Eval('state') != 'requested',
                    },
                })
        cls._error_messages.update({
                'delete_draft_canceled': ('You can not delete mandate "%s" '
                    'because it is not in draft or canceled state.'),
                })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_type():
        return 'recurrent'

    @staticmethod
    def default_state():
        return 'draft'

    @property
    def is_valid(self):
        if self.state == 'validated':
            if self.type == 'one-off':
                if not self.has_payments:
                    return True
            else:
                return True
        return False

    @property
    def sequence_type(self):
        if self.type == 'one-off':
            return 'OOFF'
        elif len(self.payments) == 1:
            return 'FRST'
        # TODO manage FNAL
        else:
            return 'RCUR'

    @classmethod
    def has_payments(self, mandates, name):
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__
        cursor = Transaction().cursor
        in_max = cursor.IN_MAX

        has_payments = dict.fromkeys([m.id for m in mandates], False)
        for i in range(0, len(mandates), in_max):
            sub_ids = [i.id for i in mandates[i:i + in_max]]
            red_sql = reduce_ids(payment.sepa_mandate, sub_ids)
            cursor.execute(*payment.select(payment.sepa_mandate, Literal(True),
                    where=red_sql,
                    group_by=payment.sepa_mandate))
            has_payments.update(cursor.fetchall())

        return {'has_payments': has_payments}

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, mandates):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('requested')
    def request(cls, mandates):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_mandate(cls, mandates):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('canceled')
    def cancel(cls, mandates):
        # TODO must be automaticaly canceled 13 months after last collection
        pass

    @classmethod
    def delete(cls, mandates):
        for mandate in mandates:
            if mandate.state not in ('draft', 'canceled'):
                cls.raise_user_error('delete_draft_canceled', mandate.rec_name)
        super(Mandate, cls).delete(mandates)
