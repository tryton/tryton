# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal
from itertools import groupby

from sql.aggregate import Count, Sum
from sql.functions import CharLength
from sql.operators import Abs

from trytond import backend
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, Workflow, fields)
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import (
    employee_field, reset_employee, set_employee)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.rpc import RPC
from trytond.tools import (
    cursor_dict, grouped_slice, reduce_ids, sortable_values,
    sqlite_apply_types)
from trytond.transaction import Transaction
from trytond.wizard import StateAction, Wizard

from .exceptions import OverpayWarning, ReconciledWarning

KINDS = [
    ('payable', 'Payable'),
    ('receivable', 'Receivable'),
    ]


class Journal(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'account.payment.journal'
    name = fields.Char('Name', required=True)
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One('company.company', "Company", required=True)
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
    __name__ = 'account.payment.group'
    _rec_name = 'number'
    number = fields.Char('Number', required=True, readonly=True)
    company = fields.Many2One(
        'company.company', "Company",
        required=True, readonly=True)
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
            ],
        order=[('date', 'ASC'), ('id', 'ASC')])
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
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

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

    def process_manual(self):
        pass

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            configuration = Configuration(1)
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                if sequence := configuration.get_multivalue(
                        'payment_group_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def copy(cls, groups, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('payments', None)
        return super().copy(groups, default=default)

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
            query = payment.select(*columns,
                where=reduce_ids(payment.group, sub_ids),
                group_by=payment.group)
            if backend.name == 'sqlite':
                sqlite_apply_types(
                    query, [None, None, 'NUMERIC', 'NUMERIC', None])
            cursor.execute(*query)
            for row in cursor_dict(cursor):
                group = cls(row['group_id'])

                result['payment_count'][group.id] = row['payment_count']
                result['payment_complete'][group.id] = \
                    not row['payment_not_complete']

                amount = row['payment_amount']
                succeeded = row['payment_amount_succeeded']

                if amount is not None and backend.name == 'sqlite':
                    amount = group.company.currency.round(amount)
                result['payment_amount'][group.id] = amount

                if succeeded is not None and backend.name == 'sqlite':
                    succeeded = group.company.currency.round(succeeded)
                result['payment_amount_succeeded'][group.id] = succeeded

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
        return self.journal.currency if self.journal else None

    @classmethod
    def search_currency(cls, name, clause):
        return [('journal.' + clause[0],) + tuple(clause[1:])]


_STATES = {
    'readonly': Eval('state') != 'draft',
    }


class Payment(Workflow, ModelSQL, ModelView):
    __name__ = 'account.payment'
    _rec_name = 'number'
    number = fields.Char("Number", required=True, readonly=True)
    reference = fields.Char("Reference", states=_STATES)
    company = fields.Many2One(
        'company.company', "Company", required=True, states=_STATES)
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
        domain=[('amount', '>=', 0)],
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
    origin = fields.Reference(
        "Origin", selection='get_origin',
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
            ('journal', '=', Eval('journal', -1)),
            ('kind', '=', Eval('kind')),
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
            ], "State", readonly=True, sort=False,
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
        cls.number.search_unaccented = False
        cls.reference.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(
                    t, (t.state, Index.Equality(cardinality='low')),
                    where=t.state.in_([
                            'draft', 'submitted', 'approved', 'processing'])),
                Index(
                    t, (t.line, Index.Range()),
                    where=t.state != 'failed'),
                })
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
                'process_wizard': {
                    'invisible': ~(
                        (Eval('state') == 'approved')
                        | ((Eval('state') == 'submitted')
                            & (Eval('kind') == 'receivable'))),
                    'icon': 'tryton-launch',
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
        cls.group.states['required'] &= Eval('process_method').in_(
            cls.process_method_with_group())

    @classmethod
    def __register__(cls, module):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        table_h = cls.__table_handler__(module)
        number_exist = table_h.column_exist('number')

        # Migration from 7.4: rename description into reference
        if table_h.column_exist('description'):
            table_h.column_rename('description', 'reference')

        super().__register__(module)

        # Migration from 7.2: add number
        if not number_exist:
            cursor.execute(*table.update([table.number], [table.id]))

    @classmethod
    def order_number(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.number), table.number]

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
        return self.journal.currency if self.journal else None

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

    def get_rec_name(self, name):
        items = [self.number]
        if self.reference:
            items.append(f'[{self.reference}]')
        return ' '.join(items)

    @classmethod
    def search_rec_name(cls, name, clause):
        _, operator, value = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('number', *clause[1:]),
            ('reference', *clause[1:]),
            ]

    @classmethod
    def view_attributes(cls):
        context = Transaction().context
        attributes = super().view_attributes()
        if context.get('kind') == 'receivable':
            attributes.append(
                ('/tree//button[@name="approve"]', 'tree_invisible', True))
        return attributes

    @classmethod
    def copy(cls, payments, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('number', None)
        default.setdefault('group', None)
        default.setdefault('approved_by')
        default.setdefault('succeeded_by')
        default.setdefault('failed_by')
        return super().copy(payments, default=default)

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        values = super().preprocess_values(mode, values)
        if mode == 'create' and not values.get('number'):
            configuration = Configuration(1)
            company_id = values.get('company', cls.default_company())
            if company_id is not None:
                if sequence := configuration.get_multivalue(
                        'payment_sequence', company=company_id):
                    values['number'] = sequence.get()
        return values

    @classmethod
    def check_modification(cls, mode, payments, values=None, external=False):
        super().check_modification(
            mode, payments, values=values, external=external)
        if mode == 'delete':
            for payment in payments:
                if payment.state != 'draft':
                    raise AccessError(gettext(
                            'account_payment.msg_payment_delete_draft',
                            payment=payment.rec_name))

    @classmethod
    def on_modification(cls, mode, payments, field_names=None):
        pool = Pool()
        Line = pool.get('account.move.line')
        super().on_modification(mode, payments, field_names=field_names)
        if mode in {'create', 'write'}:
            if not field_names or 'line' in field_names:
                if lines := Line.browse({p.line for p in payments if p.line}):
                    Line.set_payment_amount(lines)

    @classmethod
    def on_write(cls, payments, values):
        pool = Pool()
        Line = pool.get('account.move.line')
        callback = super().on_write(payments, values)
        if values.keys() & {'line', 'amount', 'state'}:
            if lines := Line.browse({p.line for p in payments if p.line}):
                callback.append(lambda: Line.set_payment_amount(lines))
        return callback

    @classmethod
    def on_delete(cls, payments):
        pool = Pool()
        Line = pool.get('account.move.line')
        callback = super().on_delete(payments)
        if lines := Line.browse({p.line for p in payments if p.line}):
            callback.append(lambda: Line.set_payment_amount(lines))
        return callback

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
        cls._check_reconciled(payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('approved')
    @set_employee('approved_by')
    def approve(cls, payments):
        cls._check_reconciled(payments)

    @classmethod
    @ModelView.button_action('account_payment.act_process_payments')
    def process_wizard(cls, payments):
        pass

    @classmethod
    def process_method_with_group(cls):
        return ['manual']

    @classmethod
    @Workflow.transition('processing')
    def process(cls, payments, group=None):
        if payments:
            if group:
                group = group()
                cls.write(payments, {
                        'group': group.id,
                        })
            # Set state before calling process method
            # as it may set a different state directly
            cls.proceed(payments)
            if group:
                getattr(group, f'process_{group.process_method}')()
            else:
                for payment in payments:
                    getattr(payment, f'process_{payment.process_method}')()
            return group

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    def proceed(cls, payments):
        cls._check_reconciled(
            [p for p in payments if p.state not in {'succeeded', 'failed'}])

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

    @classmethod
    def _check_reconciled(cls, payments):
        pool = Pool()
        Warning = pool.get('res.user.warning')
        for payment in payments:
            if payment.line and payment.line.reconciliation:
                key = Warning.format('submit_reconciled', [payment])
                if Warning.check(key):
                    raise ReconciledWarning(
                        key, gettext(
                            'account_payment.msg_payment_reconciled',
                            payment=payment.rec_name,
                            line=payment.line.rec_name))


class ProcessPayment(Wizard):
    __name__ = 'account.payment.process'
    start_state = 'process'
    process = StateAction('account_payment.act_payment_group_form')

    def _group_payment_key(self, payment):
        return (
            ('company', payment.company),
            ('journal', payment.journal),
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

        process_method_with_group = Payment.process_method_with_group()
        groups = []
        payments = sorted(
            payments, key=sortable_values(self._group_payment_key))
        for key, grouped_payments in groupby(payments,
                key=self._group_payment_key):
            def group():
                group = self._new_group(key)
                group.save()
                return group
            key = dict(key)
            process_method = key['journal'].process_method
            group = Payment.process(
                list(grouped_payments),
                group if process_method in process_method_with_group else None)
            if group:
                groups.append(group)

        if groups:
            return action, {
                'res_id': [g.id for g in groups],
                }
