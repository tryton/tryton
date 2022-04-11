# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql.aggregate import Count, Sum
from sql.operators import Abs

from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, ModelSQL, ModelView, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.rpc import RPC
from trytond.tools import (
    cursor_dict, grouped_slice, reduce_ids, sortable_values)
from trytond.transaction import Transaction
from trytond.wizard import Button, StateAction, StateView, Wizard

from .exceptions import OverpayWarning

KINDS = [
    ('payable', 'Payable'),
    ('receivable', 'Receivable'),
    ]


class Journal(DeactivableMixin, ModelSQL, ModelView):
    'Payment Journal'
    __name__ = 'account.payment.journal'
    name = fields.Char('Name', required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    process_method = fields.Selection([
            ('manual', 'Manual'),
            ], 'Process Method', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @staticmethod
    def default_currency():
        if Transaction().context.get('company'):
            Company = Pool().get('company.company')
            company = Company(Transaction().context['company'])
            return company.currency.id

    @staticmethod
    def default_company():
        return Transaction().context.get('company')


class Group(ModelSQL, ModelView):
    'Payment Group'
    __name__ = 'account.payment.group'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, readonly=True)
    company = fields.Many2One(
        'company.company', "Company",
        required=True, readonly=True, select=True)
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, readonly=True, domain=[
            ('company', '=', Eval('company', -1)),
            ])
    kind = fields.Selection(KINDS, 'Kind', required=True, readonly=True)
    payments = fields.One2Many(
        'account.payment', 'group', 'Payments', readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('journal', '=', Eval('journal', -1)),
            ])
    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"),
        'on_change_with_currency', searcher='search_currency')
    payment_count = fields.Function(fields.Integer(
            "Payment Count",
            help="The number of payments in the group."),
        'get_payment_aggregated')
    payment_amount = fields.Function(Monetary(
            "Payment Total Amount", currency='currency', digits='currency',
            help="The sum of all payment amounts."),
        'get_payment_aggregated')
    payment_amount_succeeded = fields.Function(Monetary(
            "Payment Succeeded", currency='currency', digits='currency',
            help="The sum of the amounts of the successful payments."),
        'get_payment_aggregated')
    payment_complete = fields.Function(fields.Boolean(
            "Payment Complete",
            help="All the payments in the group are complete."),
        'get_payment_aggregated', searcher='search_complete')

    process_method = fields.Function(
        fields.Selection('get_process_methods', "Process Method"),
        'on_change_with_process_method', searcher='search_process_method')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            succeed={
                'invisible': Eval('payment_complete', False),
                'depends': ['payment_complete', 'process_method'],
                },
            )

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        # Migration from 3.8: rename reference into number
        if table_h.column_exist('reference'):
            table_h.column_rename('reference', 'number')
        super(Group, cls).__register__(module_name)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def get_process_methods(cls):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        field_name = 'process_method'
        return Journal.fields_get([field_name])[field_name]['selection']

    @fields.depends('journal')
    def on_change_with_process_method(self, name=None):
        if self.journal:
            return self.journal.process_method

    @classmethod
    def search_process_method(cls, name, clause):
        return [('journal.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Config = pool.get('account.configuration')

        vlist = [v.copy() for v in vlist]
        config = Config(1)
        default_company = cls.default_company()
        for values in vlist:
            if values.get('number') is None:
                values['number'] = config.get_multivalue(
                    'payment_group_sequence',
                    company=values.get('company', default_company)).get()
        return super(Group, cls).create(vlist)

    @classmethod
    def copy(cls, groups, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('payments', None)
        return super(Group, cls).copy(groups, default=default)

    @classmethod
    @ModelView.button
    def succeed(cls, groups):
        pool = Pool()
        Payment = pool.get('account.payment')
        payments = sum((g.payments for g in groups), ())
        Payment.succeed(payments)

    @classmethod
    def _get_complete_states(cls):
        return ['succeeded', 'failed']

    @classmethod
    def get_payment_aggregated(cls, groups, names):
        pool = Pool()
        Payment = pool.get('account.payment')
        cursor = Transaction().connection.cursor()

        payment = Payment.__table__()

        # initialize result and columns
        result = defaultdict(lambda: defaultdict(lambda: None))
        columns = [
            payment.group.as_('group_id'),
            Count(payment.group).as_('payment_count'),
            Sum(payment.amount).as_('payment_amount'),
            Sum(payment.amount,
                filter_=(payment.state == 'succeeded'),
                ).as_('payment_amount_succeeded'),
            Count(payment.group,
                filter_=(~payment.state.in_(cls._get_complete_states())),
                ).as_('payment_not_complete'),
            ]

        for sub_ids in grouped_slice(groups):
            cursor.execute(*payment.select(*columns,
                where=reduce_ids(payment.group, sub_ids),
                group_by=payment.group),
                )

            for row in cursor_dict(cursor):
                group_id = row['group_id']

                result['payment_count'][group_id] = row['payment_count']
                result['payment_complete'][group_id] = \
                    not row['payment_not_complete']

                amount = row['payment_amount']
                succeeded = row['payment_amount_succeeded']

                if amount is not None:
                    # SQLite uses float for SUM
                    if not isinstance(amount, Decimal):
                        amount = Decimal(str(amount))
                    amount = cls(group_id).company.currency.round(amount)
                result['payment_amount'][group_id] = amount

                if succeeded is not None:
                    # SQLite uses float for SUM
                    if not isinstance(succeeded, Decimal):
                        succeeded = Decimal(str(succeeded))
                    succeeded = cls(group_id).company.currency.round(succeeded)
                result['payment_amount_succeeded'][group_id] = succeeded

        for key in list(result.keys()):
            if key not in names:
                del result[key]

        return result

    @classmethod
    def search_complete(cls, name, clause):
        pool = Pool()
        Payment = pool.get('account.payment')
        payment = Payment.__table__()

        query_not_completed = payment.select(payment.group,
            where=~payment.state.in_(cls._get_complete_states()),
            group_by=payment.group)

        operators = {
            '=': 'not in',
            '!=': 'in',
            }
        reverse = {
            '=': 'in',
            '!=': 'not in',
            }

        if clause[1] in operators:
            if clause[2]:
                return [('id', operators[clause[1]], query_not_completed)]
            else:
                return [('id', reverse[clause[1]], query_not_completed)]
        else:
            return []

    @fields.depends('journal')
    def on_change_with_currency(self, name=None):
        if self.journal:
            return self.journal.currency.id

    @classmethod
    def search_currency(cls, name, clause):
        return [('journal.' + clause[0],) + tuple(clause[1:])]


_STATES = {
    'readonly': Eval('state') != 'draft',
    }


class Payment(Workflow, ModelSQL, ModelView):
    'Payment'
    __name__ = 'account.payment'
    company = fields.Many2One(
        'company.company', "Company", required=True, select=True,
        states=_STATES)
    journal = fields.Many2One('account.payment.journal', 'Journal',
        required=True, states=_STATES, domain=[
            ('company', '=', Eval('company', -1)),
            ])
    currency = fields.Function(fields.Many2One('currency.currency',
            'Currency'), 'on_change_with_currency',
        searcher='search_currency')
    kind = fields.Selection(KINDS, 'Kind', required=True,
        states=_STATES)
    party = fields.Many2One(
        'party.party', "Party", required=True, states=_STATES,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    date = fields.Date('Date', required=True, states=_STATES)
    amount = Monetary(
        "Amount", currency='currency', digits='currency', required=True,
        states={
            'readonly': ~Eval('state').in_(
                If(Eval('process_method') == 'manual',
                    ['draft', 'processing'],
                    ['draft'])),
            })
    line = fields.Many2One('account.move.line', 'Line', ondelete='RESTRICT',
        domain=[
            ('move.company', '=', Eval('company', -1)),
            If(Eval('kind') == 'receivable',
                ['OR', ('debit', '>', 0), ('credit', '<', 0)],
                ['OR', ('credit', '>', 0), ('debit', '<', 0)],
                ),
            ['OR',
                ('account.type.receivable', '=', True),
                ('account.type.payable', '=', True),
                ],
            ('party', 'in', [Eval('party', None), None]),
            If(Eval('state') == 'draft',
                [
                    ('reconciliation', '=', None),
                    ('maturity_date', '!=', None),
                    ],
                []),
            ['OR',
                ('second_currency', '=', Eval('currency', None)),
                [
                    ('account.company.currency', '=', Eval('currency', None)),
                    ('second_currency', '=', None),
                    ],
                ],
            ('move_state', '=', 'posted'),
            ],
        states=_STATES)
    description = fields.Char('Description', states=_STATES)
    origin = fields.Reference(
        "Origin", selection='get_origin', select=True,
        states={
            'readonly': Eval('state') != 'draft',
            })
    group = fields.Many2One('account.payment.group', 'Group', readonly=True,
        ondelete='RESTRICT',
        states={
            'required': Eval('state').in_(['processing', 'succeeded']),
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    process_method = fields.Function(
        fields.Selection('get_process_methods', "Process Method"),
        'on_change_with_process_method', searcher='search_process_method')
    submitted_by = employee_field(
        "Submitted by",
        states=['submitted', 'processing', 'succeeded', 'failed'])
    approved_by = employee_field(
        "Approved by",
        states=['approved', 'processing', 'succeeded', 'failed'])
    succeeded_by = employee_field(
        "Success Noted by", states=['succeeded', 'processing'])
    failed_by = employee_field(
        "Failure Noted by",
        states=['failed', 'processing'])
    state = fields.Selection([
            ('draft', 'Draft'),
            ('submitted', "Submitted"),
            ('approved', 'Approved'),
            ('processing', 'Processing'),
            ('succeeded', 'Succeeded'),
            ('failed', 'Failed'),
            ], "State", readonly=True, select=True, sort=False,
        domain=[
            If(Eval('kind') == 'receivable',
                ('state', '!=', 'approved'),
                ()),
            ])

    @property
    def amount_line_paid(self):
        if self.state != 'failed':
            if self.line.second_currency:
                payment_amount = abs(self.line.amount_second_currency)
            else:
                payment_amount = abs(self.line.credit - self.line.debit)
            return max(min(self.amount, payment_amount), 0)
        return Decimal(0)

    @classmethod
    def __setup__(cls):
        super(Payment, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._transitions |= set((
                ('draft', 'submitted'),
                ('submitted', 'approved'),
                ('submitted', 'processing'),
                ('approved', 'processing'),
                ('processing', 'succeeded'),
                ('processing', 'failed'),
                ('submitted', 'draft'),
                ('approved', 'draft'),
                ('succeeded', 'failed'),
                ('succeeded', 'processing'),
                ('failed', 'succeeded'),
                ('failed', 'processing'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['submitted', 'approved']),
                    'icon': 'tryton-back',
                    'depends': ['state'],
                    },
                'submit': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-forward',
                    'depends': ['state'],
                    },
                'approve': {
                    'invisible': (
                        (Eval('state') != 'submitted')
                        | (Eval('kind') == 'receivable')),
                    'icon': 'tryton-forward',
                    'depends': ['state', 'kind'],
                    },
                'proceed': {
                    'invisible': (
                        ~Eval('state').in_(['succeeded', 'failed'])
                        | (Eval('process_method') != 'manual')),
                    'icon': 'tryton-back',
                    'depends': ['state', 'process_method'],
                    },
                'succeed': {
                    'invisible': ~Eval('state').in_(
                        ['processing', 'failed']),
                    'icon': 'tryton-ok',
                    'depends': ['state'],
                    },
                'fail': {
                    'invisible': ~Eval('state').in_(
                        ['processing', 'succeeded']),
                    'icon': 'tryton-cancel',
                    'depends': ['state'],
                    },
                })
        cls.__rpc__.update({
                'approve': RPC(
                    readonly=False, instantiate=0, fresh_session=True),
                })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_kind():
        return 'payable'

    @staticmethod
    def default_date():
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @staticmethod
    def default_state():
        return 'draft'

    @fields.depends('journal')
    def on_change_with_currency(self, name=None):
        if self.journal:
            return self.journal.currency.id

    @classmethod
    def search_currency(cls, name, clause):
        return [('journal.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def order_amount(cls, tables):
        table, _ = tables[None]
        context = Transaction().context
        column = cls.amount.sql_column(table)
        if isinstance(context.get('amount_order'), Decimal):
            return [Abs(column - abs(context['amount_order']))]
        else:
            return [column]

    @fields.depends('kind')
    def on_change_kind(self):
        self.line = None

    @fields.depends('party')
    def on_change_party(self):
        self.line = None

    @fields.depends('line',
        '_parent_line.maturity_date', '_parent_line.payment_amount')
    def on_change_line(self):
        if self.line:
            self.date = self.line.maturity_date
            self.amount = self.line.payment_amount

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return []

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()
        return [(None, '')] + [(m, get_name(m)) for m in models]

    @fields.depends('journal')
    def on_change_with_process_method(self, name=None):
        if self.journal:
            return self.journal.process_method

    @classmethod
    def search_process_method(cls, name, clause):
        return [('journal.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def get_process_methods(cls):
        pool = Pool()
        Journal = pool.get('account.payment.journal')
        field_name = 'process_method'
        return Journal.fields_get([field_name])[field_name]['selection']

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('group', None)
        default.setdefault('approved_by')
        default.setdefault('succeeded_by')
        default.setdefault('failed_by')
        return super().copy(payments, default=default)

    @classmethod
    def delete(cls, payments):
        for payment in payments:
            if payment.state != 'draft':
                raise AccessError(
                    gettext('account_payment.msg_payment_delete_draft',
                        payment=payment.rec_name))
        super(Payment, cls).delete(payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    @reset_employee('submitted_by', 'approved_by', 'succeeded_by', 'failed_by')
    def draft(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('submitted')
    @set_employee('submitted_by')
    def submit(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    @set_employee('approved_by')
    def approve(cls, payments):
        pass

    @classmethod
    @Workflow.transition('processing')
    def process(cls, payments, group):
        pool = Pool()
        Group = pool.get('account.payment.group')
        if payments:
            group = group()
            cls.write(payments, {
                    'group': group.id,
                    })
            # Set state before calling process method
            # as it may set a different state directly
            cls.proceed(payments)
            process_method = getattr(Group,
                'process_%s' % group.journal.process_method, None)
            if process_method:
                process_method(group)
                group.save()
            return group

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    def proceed(cls, payments):
        assert all(p.group for p in payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('succeeded')
    @set_employee('succeeded_by')
    def succeed(cls, payments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('failed')
    @set_employee('failed_by')
    def fail(cls, payments):
        pass


class ProcessPaymentStart(ModelView):
    'Process Payment'
    __name__ = 'account.payment.process.start'


class ProcessPayment(Wizard):
    'Process Payment'
    __name__ = 'account.payment.process'
    start = StateView('account.payment.process.start',
        'account_payment.payment_process_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Process', 'process', 'tryton-ok', default=True),
            ])
    process = StateAction('account_payment.act_payment_group_form')

    def _group_payment_key(self, payment):
        return (
            ('company', payment.company.id),
            ('journal', payment.journal.id),
            ('kind', payment.kind),
            )

    def _new_group(self, values):
        pool = Pool()
        Group = pool.get('account.payment.group')
        return Group(**values)

    def do_process(self, action):
        pool = Pool()
        Payment = pool.get('account.payment')
        Warning = pool.get('res.user.warning')
        payments = self.records

        payments = [
            p for p in payments
            if p.state == 'approved'
            or (p.state == 'submitted' and p.kind == 'receivable')]

        for payment in payments:
            if payment.line and payment.line.payment_amount < 0:
                if Warning.check(str(payment)):
                    raise OverpayWarning(str(payment),
                        gettext('account_payment.msg_payment_overpay',
                            payment=payment.rec_name,
                            line=payment.line.rec_name))

        groups = []
        payments = sorted(
            payments, key=sortable_values(self._group_payment_key))
        for key, grouped_payments in groupby(payments,
                key=self._group_payment_key):
            def group():
                group = self._new_group(dict(key))
                group.save()
                groups.append(group)
                return group
            Payment.process(list(grouped_payments), group)

        return action, {
            'res_id': [g.id for g in groups],
            }
