# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import os
import unicodedata
import uuid
from io import BytesIO
from itertools import groupby
from operator import attrgetter

import genshi
import genshi.template
# XXX fix: https://genshi.edgewall.org/ticket/582
from genshi.template.astutil import ASTCodeGenerator, ASTTransformer
from lxml import etree
from sql import Literal, Null

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import (
    Index, ModelSQL, ModelView, Unique, Workflow, dualmethod, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.account_payment.exceptions import ProcessError
from trytond.modules.company import CompanyReport
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.tools import (
    grouped_slice, is_full_text, lstrip_wildcard, reduce_ids, sortable_values)
from trytond.transaction import Transaction

from .sepa_handler import CAMT054

if not hasattr(ASTCodeGenerator, 'visit_NameConstant'):
    def visit_NameConstant(self, node):
        if node.value is None:
            self._write('None')
        elif node.value is True:
            self._write('True')
        elif node.value is False:
            self._write('False')
        else:
            raise Exception("Unknown NameConstant %r" % (node.value,))
    ASTCodeGenerator.visit_NameConstant = visit_NameConstant
if not hasattr(ASTTransformer, 'visit_NameConstant'):
    # Re-use visit_Name because _clone is deleted
    ASTTransformer.visit_NameConstant = ASTTransformer.visit_Name

if config.getboolean('account_payment_sepa', 'filestore', default=False):
    file_id = 'message_file_id'
    store_prefix = config.get(
        'account_payment_sepa', 'store_prefix', default=None)
else:
    file_id = None
    store_prefix = None

INITIATOR_IDS = [
    (None, ''),
    ('eu_at_02', "SEPA Creditor Identifier"),
    ('be_vat', "Belgian Enterprise Number"),
    ('es_vat', "Spanish VAT Number"),
    ]


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'
    company_party = fields.Function(fields.Many2One(
            'party.party', "Company Party",
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'on_change_with_company_party')
    sepa_bank_account_number = fields.Many2One('bank.account.number',
        'Bank Account Number', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        domain=[
            ('type', '=', 'iban'),
            ('account.owners', '=', Eval('company_party', -1)),
            ])
    sepa_payable_flavor = fields.Selection([
            (None, ''),
            ('pain.001.001.03', 'pain.001.001.03'),
            ('pain.001.001.05', 'pain.001.001.05'),
            ('pain.001.003.03', 'pain.001.003.03'),
            ], 'Payable Flavor', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        translate=False)
    sepa_receivable_flavor = fields.Selection([
            (None, ''),
            ('pain.008.001.02', 'pain.008.001.02'),
            ('pain.008.001.04', 'pain.008.001.04'),
            ('pain.008.003.02', 'pain.008.003.02'),
            ], 'Receivable Flavor', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        translate=False)
    sepa_payable_initiator_id = fields.Selection(
        INITIATOR_IDS, "SEPA Payable Initiator Identifier",
        states={
            'invisible': Eval('process_method') != 'sepa',
            },
        help="The identifier used for the initiating party.")
    sepa_receivable_initiator_id = fields.Selection(
        INITIATOR_IDS, "SEPA Receivable Initiator Identifier",
        states={
            'invisible': Eval('process_method') != 'sepa',
            },
        help="The identifier used for the initiating party.")
    sepa_batch_booking = fields.Boolean('Batch Booking', states={
            'invisible': Eval('process_method') != 'sepa',
            })
    sepa_charge_bearer = fields.Selection([
            ('DEBT', 'Debtor'),
            ('CRED', 'Creditor'),
            ('SHAR', 'Shared'),
            ('SLEV', 'Service Level'),
            ], 'Charge Bearer', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            })

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        sepa_method = ('sepa', 'SEPA')
        if sepa_method not in cls.process_method.selection:
            cls.process_method.selection.append(sepa_method)

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()
        super().__register__(module_name)

        # Migration from 5.4: sepa identifier merged into eu_at_02
        for name in {'payable', 'receivable'}:
            column = getattr(sql_table, 'sepa_%s_initiator_id' % name)
            cursor.execute(*sql_table.update(
                    columns=[column],
                    values=['eu_at_02'],
                    where=column == 'sepa'))

        # Migration from 6.8: es_nif renamed into es_vat
        cursor.execute(*sql_table.update(
                [sql_table.sepa_payable_initiator_id],
                ['es_vat'],
                where=sql_table.sepa_payable_initiator_id == 'es_nif'))
        cursor.execute(*sql_table.update(
                [sql_table.sepa_receivable_initiator_id],
                ['es_vat'],
                where=sql_table.sepa_receivable_initiator_id == 'es_nif'))

    @classmethod
    def default_company_party(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            return Company(company_id).party.id

    @fields.depends('company')
    def on_change_with_company_party(self, name=None):
        return self.company.party if self.company else None

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


class Group(metaclass=PoolMeta):
    __name__ = 'account.payment.group'
    sepa_messages = fields.One2Many('account.payment.sepa.message', 'origin',
        'SEPA Messages', readonly=True,
        domain=[('company', '=', Eval('company', -1))],
        states={
            'invisible': ~Eval('sepa_messages'),
            })
    sepa_id = fields.Char("SEPA ID", readonly=True, size=35,
        states={
            'invisible': ~Eval('sepa_id'),
            })

    @classmethod
    def __setup__(cls):
        super(Group, cls).__setup__()
        cls._buttons.update({
                'sepa_generate_message': {
                    'invisible': Eval('process_method') != 'sepa',
                    'depends': ['process_method'],
                    },
                })

    def get_sepa_template(self):
        if self.kind == 'payable':
            return loader.load('%s.xml' % self.journal.sepa_payable_flavor)
        elif self.kind == 'receivable':
            return loader.load('%s.xml' % self.journal.sepa_receivable_flavor)

    def process_sepa(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        Mandate = pool.get('account.payment.sepa.mandate')
        if self.kind == 'receivable':
            payments = sorted(self.payments, key=attrgetter('date', 'id'))
            mandates = Payment.get_sepa_mandates(payments)
            Mandate.lock(list(filter(None, mandates)))
            sequence_types = {}
            for payment, mandate in zip(payments, mandates):
                if not mandate:
                    raise ProcessError(
                        gettext('account_payment_sepa'
                            '.msg_payment_process_no_mandate',
                            payment=payment.rec_name))
                sequence_type = sequence_types.get(mandate)
                if not sequence_type:
                    sequence_type = mandate.sequence_type
                    if sequence_type == 'FRST':
                        sequence_types[mandate] = 'RCUR'
                    else:
                        sequence_types[mandate] = sequence_type
                payment.sepa_mandate = mandate
                payment.sepa_mandate_sequence_type = sequence_type
            Payment.save(payments)
        for payment in self.payments:
            if not payment.sepa_bank_account_number:
                raise ProcessError(
                    gettext('account_payment_sepa'
                        '.msg_payment_process_no_iban',
                        payment=payment.rec_name))
            if not payment.sepa_bank_account_number.account.bank:
                bank_account = payment.sepa_bank_account_number.account
                raise ProcessError(
                    gettext('account_payment_sepa'
                        '.msg_payment_process_no_bank',
                        payment=payment.rec_name,
                        bank_account=bank_account.rec_name))
        to_write = []
        for key, payments in self.sepa_payments:
            to_write.append(payments)
            to_write.append({
                    'sepa_info_id': self.sepa_group_payment_id(key),
                    })
        if to_write:
            Payment.write(*to_write)
        self.sepa_id = uuid.uuid4().hex
        self.sepa_generate_message(_save=False)

    @dualmethod
    @ModelView.button
    def sepa_generate_message(cls, groups, _save=True):
        pool = Pool()
        Message = pool.get('account.payment.sepa.message')
        for group in groups:
            if group.journal.process_method != 'sepa':
                continue
            tmpl = group.get_sepa_template()
            if not tmpl:
                raise NotImplementedError
            if not group.sepa_messages:
                group.sepa_messages = ()
            message = tmpl.generate(group=group,
                datetime=datetime, normalize=unicodedata.normalize,
                ).filter(remove_comment).render().encode('utf8')
            message = Message(message=message, type='out', state='waiting',
                company=group.company)
            group.sepa_messages += (message,)
        if _save:
            cls.save(groups)

    @property
    def sepa_initiating_party(self):
        return self.company.party

    def sepa_group_payment_key(self, payment):
        key = (
            ('payment_info', payment.sepa_info_id),
            ('date', payment.date),
            )
        if self.kind == 'receivable':
            key += (('sequence_type', payment.sepa_mandate_sequence_type),)
            key += (('scheme', payment.sepa_mandate.scheme),)
        return key

    def sepa_group_payment_id(self, key):
        return key['payment_info'] or uuid.uuid4().hex

    @property
    def sepa_payments(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        keyfunc = self.sepa_group_payment_key
        # re-browse to align cache
        payments = Payment.browse(sorted(
                self.payments, key=sortable_values(keyfunc)))
        for key, grouped_payments in groupby(payments, key=keyfunc):
            yield dict(key), list(grouped_payments)

    @property
    def sepa_message_id(self):
        return self.sepa_id or self.number

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        domain = super().search_rec_name(name, clause)
        return [bool_op,
            domain,
            ('sepa_id', operator, code_value, *extra),
            ]


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    sepa_mandate = fields.Many2One('account.payment.sepa.mandate', 'Mandate',
        ondelete='RESTRICT',
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': ((Eval('process_method') != 'sepa')
                | (Eval('kind') != 'receivable')),
            },
        domain=[
            ('party', '=', Eval('party', -1)),
            ('company', '=', Eval('company', -1)),
            If(Eval('state') == 'draft',
                ('state', '=', 'validated'),
                (),
                )
            ])
    sepa_mandate_sequence_type = fields.Char('Mandate Sequence Type',
        readonly=True)
    sepa_return_reason_code = fields.Char('Return Reason Code', readonly=True,
        states={
            'invisible': ((Eval('process_method') != 'sepa')
                | (~Eval('sepa_return_reason_code')
                    & (Eval('state') != 'failed'))),
            })
    sepa_return_reason_information = fields.Text('Return Reason Information',
        readonly=True,
        states={
            'invisible': ((Eval('process_method') != 'sepa')
                | (~Eval('sepa_return_reason_information')
                    & (Eval('state') != 'failed'))),
            })
    sepa_end_to_end_id = fields.Function(fields.Char('SEPA End To End ID'),
        'get_sepa_end_to_end_id', searcher='search_end_to_end_id')
    sepa_instruction_id = fields.Function(fields.Char('SEPA Instruction ID'),
        'get_sepa_instruction_id', searcher='search_sepa_instruction_id')
    sepa_info_id = fields.Char("SEPA Info ID", readonly=True, size=35,
        states={
            'invisible': ~Eval('sepa_info_id'),
            })

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('sepa_mandate_sequence_type', None)
        return super(Payment, cls).copy(payments, default=default)

    @classmethod
    def get_sepa_mandates(cls, payments):
        mandates = []
        for payment in payments:
            if payment.sepa_mandate:
                if payment.sepa_mandate.is_valid:
                    mandate = payment.sepa_mandate
                else:
                    mandate = None
            else:
                for mandate in payment.party.sepa_mandates_for(payment):
                    if mandate.is_valid:
                        break
                else:
                    mandate = None
            mandates.append(mandate)
        return mandates

    def get_sepa_end_to_end_id(self, name):
        return str(self.id)

    @classmethod
    def search_end_to_end_id(cls, name, domain):
        table = cls.__table__()
        _, operator, value = domain
        cast = cls.sepa_end_to_end_id._field.sql_type().base
        Operator = fields.SQL_OPERATORS[operator]
        query = table.select(table.id,
            where=Operator(table.id.cast(cast), value))
        return [('id', 'in', query)]

    get_sepa_instruction_id = get_sepa_end_to_end_id
    search_sepa_instruction_id = search_end_to_end_id

    @property
    def sepa_remittance_information(self):
        if self.description:
            return self.description
        elif self.line and self.line.move_origin:
            return getattr(self.line.move_origin, 'rec_name', '')

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

    @property
    def rejected(self):
        return (self.state == 'failed'
            and self.sepa_return_reason_code
            and self.sepa_return_reason_information == '/RTYP/RJCT')

    def _get_clearing_move(self, date=None):
        if not date:
            date = Transaction().context.get('date_value')
        return super()._get_clearing_move(date=date)

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//separator[@id="sepa_return_reason"]', 'states', {
                    'invisible': ((Eval('process_method') != 'sepa')
                        | (Eval('state') != 'failed')),
                    }),
            ]

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        code_value = operand
        if operator.endswith('like') and is_full_text(operand):
            code_value = lstrip_wildcard(operand)
        domain = super().search_rec_name(name, clause)
        return [bool_op,
            domain,
            ('sepa_info_id', operator, code_value, *extra),
            ]


class Mandate(Workflow, ModelSQL, ModelView):
    'SEPA Mandate'
    __name__ = 'account.payment.sepa.mandate'
    party = fields.Many2One(
        'party.party', "Party", required=True,
        states={
            'readonly': Eval('state').in_(
                ['requested', 'validated', 'cancelled']),
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    account_number = fields.Many2One('bank.account.number', 'Account Number',
        ondelete='RESTRICT',
        states={
            'readonly': (
                Eval('state').in_(['validated', 'cancelled'])
                | ~Eval('party')),
            'required': Eval('state') == 'validated',
            },
        domain=[
            ('type', '=', 'iban'),
            ('account.owners', '=', Eval('party', -1)),
            ])
    identification = fields.Char('Identification', size=35,
        states={
            'readonly': Eval('identification_readonly', True),
            'required': Eval('state') == 'validated',
            })
    identification_readonly = fields.Function(fields.Boolean(
            'Identification Readonly'), 'get_identification_readonly')
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    type = fields.Selection([
            ('recurrent', 'Recurrent'),
            ('one-off', 'One-off'),
            ], 'Type',
        states={
            'readonly': Eval('state').in_(['validated', 'cancelled']),
            })
    sequence_type_rcur = fields.Boolean(
        "Always use RCUR",
        states={
            'invisible': Eval('type') == 'one-off',
            })
    scheme = fields.Selection([
            ('CORE', 'Core'),
            ('B2B', 'Business to Business'),
            ], 'Scheme', required=True,
        states={
            'readonly': Eval('state').in_(['validated', 'cancelled']),
            })
    scheme_string = scheme.translated('scheme')
    signature_date = fields.Date('Signature Date',
        states={
            'readonly': Eval('state').in_(['validated', 'cancelled']),
            'required': Eval('state') == 'validated',
            })
    state = fields.Selection([
            ('draft', 'Draft'),
            ('requested', 'Requested'),
            ('validated', 'Validated'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, sort=False)
    payments = fields.One2Many('account.payment', 'sepa_mandate', 'Payments')
    has_payments = fields.Function(fields.Boolean('Has Payments'),
        'get_has_payments')
    is_first_payment = fields.Function(
        fields.Boolean("Is First Payment"), 'get_is_first_payment')

    @classmethod
    def __setup__(cls):
        super(Mandate, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'requested'),
                ('requested', 'validated'),
                ('validated', 'cancelled'),
                ('requested', 'cancelled'),
                ('requested', 'draft'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(
                        ['requested', 'validated']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') != 'requested',
                    'depends': ['state'],
                    },
                'request': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'validate_mandate': {
                    'invisible': Eval('state') != 'requested',
                    'depends': ['state'],
                    },
                })
        t = cls.__table__()
        cls._sql_constraints = [
            ('identification_unique', Unique(t, t.company, t.identification),
                'account_payment_sepa.msg_mandate_unique_id'),
            ]
        cls._sql_indexes.add(
            Index(
                t, (t.state, Index.Equality(cardinality='low')),
                where=t.state.in_(['draft', 'requested'])))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        super().__register__(module_name)

        # Migration from 5.6: rename state canceled to cancelled
        cursor.execute(*table.update(
                [table.state], ['cancelled'],
                where=table.state == 'canceled'))

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_company(self):
        self.identification_readonly = self.default_identification_readonly(
            company=self.company.id if self.company else None)

    @staticmethod
    def default_type():
        return 'recurrent'

    @classmethod
    def default_sequence_type_rcur(cls):
        return False

    @staticmethod
    def default_scheme():
        return 'CORE'

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def default_identification_readonly(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        config = Configuration(1)
        return bool(config.get_multivalue('sepa_mandate_sequence', **pattern))

    def get_identification_readonly(self, name):
        return bool(self.identification)

    def get_rec_name(self, name):
        name = '(%s)' % self.id
        if self.identification:
            name = self.identification
        if self.account_number:
            name += ' @ %s' % self.account_number.rec_name
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('identification',) + tuple(clause[1:]),
            ('account_number',) + tuple(clause[1:]),
            ]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        vlist = [v.copy() for v in vlist]
        default_company = cls.default_company()
        for values in vlist:
            if not values.get('identification'):
                sequence = config.get_multivalue(
                    'sepa_mandate_sequence',
                    company=values.get('company', default_company))
                if sequence:
                    values['identification'] = sequence.get()
            # Prevent raising false unique constraint
            if values.get('identification') == '':
                values['identification'] = None
        return super(Mandate, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        args = []
        for mandates, values in zip(actions, actions):
            # Prevent raising false unique constraint
            if values.get('identification') == '':
                values = values.copy()
                values['identification'] = None
            args.extend((mandates, values))
        super(Mandate, cls).write(*args)

    @classmethod
    def copy(cls, mandates, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('payments', [])
        default.setdefault('signature_date', None)
        default.setdefault('identification', None)
        return super(Mandate, cls).copy(mandates, default=default)

    @property
    def is_valid(self):
        if self.state == 'validated' and self.account_number.active:
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
        elif not self.sequence_type_rcur and self.is_first_payment:
            return 'FRST'
        # TODO manage FNAL
        else:
            return 'RCUR'

    @classmethod
    def get_has_payments(cls, mandates, name):
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()
        cursor = Transaction().connection.cursor()

        has_payments = dict.fromkeys([m.id for m in mandates], False)
        for sub_ids in grouped_slice(mandates):
            red_sql = reduce_ids(payment.sepa_mandate, sub_ids)
            cursor.execute(*payment.select(payment.sepa_mandate, Literal(True),
                    where=red_sql,
                    group_by=payment.sepa_mandate))
            has_payments.update(cursor)

        return has_payments

    @classmethod
    def get_is_first_payment(cls, mandates, name):
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()
        cursor = Transaction().connection.cursor()

        is_first = dict.fromkeys([m.id for m in mandates], True)
        for sub_ids in grouped_slice(mandates):
            red_sql = reduce_ids(payment.sepa_mandate, sub_ids)
            cursor.execute(*payment.select(
                    payment.sepa_mandate, Literal(False),
                    where=red_sql
                    & (payment.sepa_mandate_sequence_type != Null)
                    & ~(  # Same as property rejected
                        (payment.state == 'failed')
                        & ((payment.sepa_return_reason_code != Null)
                            | (payment.sepa_return_reason_code != ''))
                        & (payment.sepa_return_reason_information
                            == '/RTYP/RJCT')),
                    group_by=payment.sepa_mandate))
            is_first.update(cursor)
        return is_first

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
    @Workflow.transition('cancelled')
    def cancel(cls, mandates):
        # TODO must be automaticaly cancelled 13 months after last collection
        pass

    @classmethod
    def delete(cls, mandates):
        for mandate in mandates:
            if mandate.state not in ('draft', 'cancelled'):
                raise AccessError(
                    gettext('account_payment_sepa'
                        '.msg_mandate_delete_draft_cancelled',
                        mandate=mandate.rec_name))
        super(Mandate, cls).delete(mandates)


class MandateReport(CompanyReport):
    __name__ = 'account.payment.sepa.mandate'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['gettext'] = gettext
        return context


class Message(Workflow, ModelSQL, ModelView):
    'SEPA Message'
    __name__ = 'account.payment.sepa.message'
    _states = {
        'readonly': Eval('state') != 'draft',
        }
    message = fields.Binary('Message', filename='filename',
        file_id=file_id, store_prefix=store_prefix,
        states=_states)
    message_file_id = fields.Char("Message File ID", readonly=True)
    filename = fields.Function(fields.Char('Filename'), 'get_filename')
    type = fields.Selection([
            ('in', 'IN'),
            ('out', 'OUT'),
            ], 'Type', required=True, states=_states)
    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    origin = fields.Reference("Origin", selection='get_origin', states=_states)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], "State", readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super(Message, cls).__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t, (t.state, Index.Equality(cardinality='low')),
                where=t.state.in_(['draft', 'waiting'])))
        cls._transitions |= {
            ('draft', 'waiting'),
            ('waiting', 'done'),
            ('waiting', 'draft'),
            ('draft', 'cancelled'),
            ('waiting', 'cancelled'),
            }
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft', 'waiting']),
                    'depends': ['state'],
                    },
                'draft': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                'wait': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'do': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()

        super(Message, cls).__register__(module_name)

        # Migration from 5.6: rename state canceled to cancelled
        cursor.execute(*table.update(
                [table.state], ['cancelled'],
                where=table.state == 'canceled'))

    @staticmethod
    def default_type():
        return 'in'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    def get_filename(self, name):
        pool = Pool()
        Group = pool.get('account.payment.group')
        if isinstance(self.origin, Group):
            return self.origin.rec_name + '.xml'

    @staticmethod
    def _get_origin():
        'Return list of Model names for origin Reference'
        return ['account.payment.group']

    @classmethod
    def get_origin(cls):
        IrModel = Pool().get('ir.model')
        get_name = IrModel.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, messages):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, messages):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, messages):
        for message in messages:
            if message.type == 'in':
                message.parse()
            else:
                message.send()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, messages):
        pass

    @staticmethod
    def _get_handlers():
        pool = Pool()
        Payment = pool.get('account.payment')
        return {
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.01':
            lambda f: CAMT054(f, Payment),
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.02':
            lambda f: CAMT054(f, Payment),
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.03':
            lambda f: CAMT054(f, Payment),
            'urn:iso:std:iso:20022:tech:xsd:camt.054.001.04':
            lambda f: CAMT054(f, Payment),
            }

    @staticmethod
    def get_namespace(message):
        f = BytesIO(message)
        for _, element in etree.iterparse(f, events=('start',)):
            tag = etree.QName(element)
            if tag.localname == 'Document':
                return tag.namespace

    def parse(self):
        f = BytesIO(self.message)
        namespace = self.get_namespace(self.message)
        handlers = self._get_handlers()
        if namespace not in handlers:
            raise  # TODO UserError
        handlers[namespace](f)

    def send(self):
        pass
