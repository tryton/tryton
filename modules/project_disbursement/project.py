# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from sql.operators import Abs

from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Id
from trytond.transaction import Transaction

from .exceptions import DisbursementError

_disbursment_sequence = fields.Many2One(
    'ir.sequence', "Disbursement Sequence", required=True,
    domain=[
        ('sequence_type', '=',
            Id('project_disbursement', 'sequence_type_disbursement')),
        ],
    help="Used to generate the disbursement number.")


class Configuration(metaclass=PoolMeta):
    __name__ = 'project.configuration'

    disbursement_sequence = fields.MultiValue(_disbursment_sequence)

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'disbursement_sequence':
            return pool.get('project.configuration.sequence')
        return super().multivalue_model(field)

    @classmethod
    def default_disbursement_sequence(cls, **pattern):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'project_disbursement', 'sequence_disbursement')
        except KeyError:
            return None


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'project.configuration.sequence'

    disbursement_sequence = _disbursment_sequence


class Work(metaclass=PoolMeta):
    __name__ = 'project.work'

    account_disbursement = fields.Many2One(
        'account.account', "Account Disbursement",
        domain=[
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'invisible': Eval('type') != 'project',
            },
        help="Leave empty for the default account.")
    disbursement_journals = fields.One2Many(
        'project.disbursement.journal', 'work', "Disbursement Journals",
        states={
            'invisible': Eval('type') != 'project',
            })
    disbursements = fields.One2Many(
        'project.disbursement', 'work', "Disbursements",
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'editable': Bool(Eval('company', None)),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.company.states['editable'] &= ~Eval('disbursements', [])

    @classmethod
    def _get_amount_to_invoice(cls, works):
        pool = Pool()
        Currency = pool.get('currency.currency')
        amounts = super()._get_amount_to_invoice(works)
        for work in works:
            for disbursement in work.disbursements:
                if disbursement.state == 'paid':
                    amounts[work.id] += Currency.compute(
                        disbursement.currency, disbursement.amount_to_invoice,
                        work.company.currency)
        return amounts

    def _get_lines_to_invoice(self):
        lines = super()._get_lines_to_invoice()
        for disbursement in self.disbursements:
            if disbursement.state == 'paid' and disbursement.amount_to_invoice:
                lines.append({
                        'product': None,
                        'account': disbursement.account,
                        'quantity': 1,
                        'unit': None,
                        'unit_price': disbursement.amount_to_invoice,
                        'origin': disbursement,
                        'origins': [],
                        'description': disbursement.description,
                        })
        return lines

    def _group_lines_to_invoice_key(self, line):
        return super()._group_lines_to_invoice_key(line) + (
            ('account', line.get('account')),
            ('origin', line.get('origin')),
            )


class OpenInvoice(metaclass=PoolMeta):
    __name__ = 'project.open_invoice'

    def do_open_(self, action):
        works = self.model.search([
                ('parent', 'child_of', list(map(int, self.records))),
                ])
        action, data = super().do_open_(action)
        invoice_ids = set(data.get('res_id', []))
        for work in works:
            for disbursement in work.disbursements:
                for invoice_line in disbursement.invoice_lines:
                    if invoice_line.invoice:
                        invoice_ids.add(invoice_line.invoice.id)
        data['res_id'] = list(invoice_ids)
        return action, data


class Disbursement(Workflow, ModelSQL, ModelView):
    __name__ = 'project.disbursement'
    _rec_name = 'number'

    _states = {
        'readonly': Eval('state') != 'draft',
        }

    number = fields.Char("Number", readonly=True)
    work = fields.Many2One(
        'project.work', "Work", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        states={
            'readonly': _states['readonly'],
            'editable': Bool(Eval('company', None)),
            })
    company = fields.Many2One(
        'company.company', "Company", required=True, states=_states)
    description = fields.Char("Description", states=_states)

    reference = fields.Char("Reference", states=_states)
    reference_type = fields.Selection(
        'get_reference_types', "Reference Type", states=_states)

    payee = fields.Many2One(
        'party.party', "Payee", required=True, states=_states)
    payment_date = fields.Date("Date", required=True, states=_states)

    currency = fields.Many2One(
        'currency.currency', "Currency",
        required=True, states=_states)
    amount = Monetary(
        "Amount", currency='currency', digits='currency',
        required=True, states=_states,
        domain=[
            ('amount', '>', 0),
            ])

    attachments = fields.One2Many(
        'ir.attachment', 'resource', "Attachments",
        filter=[
            ('type', '=', 'data'),
            ])

    payments = fields.One2Many(
        'account.payment', 'origin', "Payments", readonly=True,
        domain=[
            ('kind', '=', 'payable'),
            ])
    invoice_lines = fields.One2Many(
        'account.invoice.line', 'origin', "Invoice Lines", readonly=True)

    validated_by = employee_field(
        "Validated By",
        states=['validated', 'paid', 'cancelled'])

    state = fields.Selection([
            ('draft', "Draft"),
            ('validated', "Validated"),
            ('paid', "Paid"),
            ('cancelled', "Cancelled"),
            ], "State", readonly=True, required=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('draft', 'validated'),
            ('draft', 'cancelled'),
            ('validated', 'validated'),
            ('validated', 'paid'),
            ('validated', 'cancelled'),
            ('paid', 'validated'),
            ('cancelled', 'draft'),
            }
        cls._buttons.update(
            draft={
                'invisible': Eval('state') != 'cancelled',
                'depends': ['state'],
                },
            validate_disbursement={
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            process={
                'invisible': ~Eval('state').in_(['validated', 'paid']),
                'depends': ['state'],
                },
            cancel={
                'invisible': ~Eval('state').in_(['draft', 'validated']),
                'depends': ['state'],
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('company', 'currency')
    def on_change_company(self):
        if self.company and not self.currency:
            self.currency = self.company.currency

    @fields.depends('reference', 'reference_type')
    def on_change_with_reference(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        if (reference := self.reference) and (type := self.reference_type):
            reference = getattr(
                Payment, f'_format_reference_{type}')(reference)
        return reference

    @classmethod
    def get_reference_types(cls):
        pool = Pool()
        Payment = pool.get('account.payment')
        return Payment.fields_get(
            ['reference_type'])['reference_type']['selection']

    @classmethod
    def order_amount(cls, tables):
        context = Transaction().context
        column = cls.amount.sql_column(tables, cls)
        if isinstance(context.get('amount_order'), Decimal):
            return [Abs(column - abs(context['amount_order']))]
        else:
            return [column]

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def _number_sequence(cls, **pattern):
        pool = Pool()
        Configuration = pool.get('project.configuration')
        config = Configuration(1)
        return config.get_multivalue('disbursement_sequence', **pattern)

    @classmethod
    def preprocess_values(cls, mode, values):
        values = super().preprocess_values(mode, values)
        if mode == 'create':
            if not values.get('number'):
                if sequence := cls._number_sequence():
                    values['number'] = sequence.get()
        return values

    @classmethod
    def copy(cls, disbursements, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('number')
        return super().copy(disbursements, default=default)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('validated_by')
    def draft(cls, disbursements):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    @set_employee('validated_by')
    def validate_disbursement(cls, disbursements):
        pool = Pool()
        Payment = pool.get('account.payment')
        payments = []
        for disbursement in disbursements:
            if payment := disbursement._get_payment():
                payments.append(payment)
        Payment.save(payments)

    def _get_payment(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        amount = self.amount
        for payment in self.payments:
            if payment.state != 'failed':
                amount -= payment.amount
        if amount > 0:
            return Payment(
                company=self.company,
                journal=self._get_journal(),
                kind='payable',
                party=self.payee,
                date=self.payment_date,
                amount=amount,
                origin=self,
                )

    def _get_journal(self, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        pattern['currency'] = self.currency.id
        work = self.work
        while work:
            if work.type == 'project':
                for disbursement_journal in work.disbursement_journals:
                    if disbursement_journal.match(pattern):
                        return disbursement_journal.journal
            work = work.parent

    @property
    def account(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        work = self.work
        while work:
            if work.type == 'project':
                if work.account_disbursement:
                    return work.account_disbursement
            work = work.parent
        configuration = Configuration(1)
        return configuration.get_multivalue(
            'default_account_disbursement',
            company=self.company.id)

    @property
    def is_paid(self):
        amount_paid = sum(
            p.amount for p in self.payments if p.state == 'succeeded')
        return self.amount <= amount_paid

    @classmethod
    @ModelView.button
    def process(cls, disbursements):
        cls.lock(disbursements)
        paid, validated = [], []
        for disbursement in disbursements:
            if disbursement.is_paid and disbursement.state != 'paid':
                paid.append(disbursement)
            elif disbursement.state in {'validated', 'paid'}:
                validated.append(disbursement)
        if paid:
            cls.paid(paid)
        if validated:
            cls.validate_disbursement(validated)

    @classmethod
    @Workflow.transition('paid')
    def paid(cls, disbursements):
        pass

    @property
    def amount_to_invoice(self):
        amount = self.amount
        for line in self.invoice_lines:
            if not line.invoice or line.invoice.state != 'cancelled':
                amount -= line.amount
        return max(amount, 0)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, disbursements):
        pool = Pool()
        Payment = pool.get('account.payment')
        to_delete = []
        for disbursement in disbursements:
            for payment in disbursement.payments:
                if payment.state not in {'draft', 'submitted'}:
                    raise DisbursementError(gettext(
                            'project_disbursement'
                            '.msg_disbursement_cancel_payment',
                            disbursement=disbursement.rec_name,
                            payment=payment.rec_name))
                elif payment.state == 'failed':
                    continue
                else:
                    to_delete.append(payment)
        if to_delete:
            Payment.draft(to_delete)
            Payment.delete(to_delete)


class DisbursementJournal(
        sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    __name__ = 'project.disbursement.journal'

    work = fields.Many2One(
        'project.work', "Work", required=True,
        domain=[
            ('type', '=', 'project'),
            ])
    currency = fields.Many2One('currency.currency', "Currency", required=True)
    journal = fields.Many2One(
        'account.payment.journal', "Journal", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    company = fields.Function(fields.Many2One(
            'company.company', "Company"),
        'on_change_with_company')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('work')

    @fields.depends('work', '_parent_work.company')
    def on_change_with_company(self, name=None):
        return self.work.company if self.work else None
