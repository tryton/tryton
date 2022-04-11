# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import ROUND_DOWN, Decimal
from itertools import groupby

from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.i18n import gettext
from trytond.model import (
    ModelSQL, ModelView, Unique, fields, sequence_ordered, tree)
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If
from trytond.rpc import RPC
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import BudgetValidationError


class AmountMixin:
    __slots__ = ()
    actual_amount = fields.Function(
        Monetary(
            "Actual Amount", currency='currency', digits='currency',
            help="The total amount booked against the budget line."),
        'get_amount')
    percentage = fields.Function(
        fields.Numeric(
            "Percentage", digits=(16, 4),
            help="The percentage of booked amount of the budget line."),
        'get_amount')

    @classmethod
    def view_attributes(cls):
        return [
            ('/tree/field[@name="ratio"]', 'visual',
                If(Eval('ratio') & (Eval('ratio', 0) > 1),
                    If(Eval('actual_amount', 0) > 0, 'danger', ''),
                    If(Eval('actual_amount', 0) < 0, 'success', ''))),
            ]

    @classmethod
    def get_amount(cls, records, names):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        records = cls.browse(sorted(records, key=cls._get_amount_group_key))
        balances = defaultdict(Decimal)
        for keys, grouped_records in groupby(
                records, key=cls._get_amount_group_key):
            for sub_records in grouped_slice(list(grouped_records)):
                cursor.execute(*cls._get_amount_query(
                        sub_records, dict(keys)))
                balances.update(cursor)

        total = {n: {} for n in names}
        for record in records:
            balance = balances[record.id]
            # SQLite uses float for SUM
            if not isinstance(balance, Decimal):
                balance = Decimal(str(balance))
            if 'actual_amount' in names:
                total['actual_amount'][record.id] = record.currency.round(
                    balance)
            if 'percentage' in names:
                if not record.total_amount:
                    percentage = None
                elif not balance:
                    percentage = Decimal('0.0000')
                else:
                    percentage = balance / record.total_amount
                    percentage = percentage.quantize(Decimal('.0001'))
                total['percentage'][record.id] = percentage
        return total

    @classmethod
    def _get_amount_group_key(cls, record):
        raise NotImplementedError

    @classmethod
    def _get_amount_query(cls, records, context):
        raise NotImplementedError


class BudgetMixin:
    __slots__ = ()
    name = fields.Char("Name", required=True)
    company = fields.Many2One(
        'company.company', "Company", required=True, select=True,
        states={
            'readonly': Eval('company') & Eval('lines', [-1]),
            },
        help="The company that the budget is associated with.")
    lines = None
    root_lines = None

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def copy(cls, budgets, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('lines')
        return super().copy(budgets, default=default)


class BudgetLineMixin(
        tree(name='current_name', separator='\\'), sequence_ordered(),
        AmountMixin):
    __slots__ = ()
    budget = None
    name = fields.Char(
        "Name",
        states={
            'required': ~Eval('account'),
            'invisible': Bool(Eval('account')),
            })
    account = None
    current_name = fields.Function(
        fields.Char("Current Name"),
        'on_change_with_current_name', searcher='search_current_name')

    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'on_change_with_company')
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')

    amount = Monetary(
        "Amount", currency='currency', digits='currency',
        help="The amount allocated to the budget line.")
    total_amount = fields.Function(
        Monetary(
            "Total Amount", currency='currency', digits='currency',
            help="The total amount allocated to "
            "the budget line and its children."),
        'get_total_amount')

    left = fields.Integer("Left", required=True, select=True)
    right = fields.Integer("Right", required=True, select=True)

    @classmethod
    def __setup__(cls):
        cls.parent = fields.Many2One(
            cls.__name__, "Parent", select=True,
            left='left', right='right', ondelete='CASCADE',
            domain=[
                ('budget', '=', Eval('budget', -1)),
                ],
            help="Used to add structure above the budget.")
        cls.children = fields.One2Many(
            cls.__name__, 'parent', "Children",
            domain=[
                ('budget', '=', Eval('budget', -1)),
                ],
            help="Used to add structure below the budget.")
        super().__setup__()
        cls.__access__.add('budget')

    @classmethod
    def default_left(cls):
        return 0

    @classmethod
    def default_right(cls):
        return 0

    @fields.depends('budget', '_parent_budget.company')
    def on_change_with_company(self, name=None):
        if self.budget and self.budget.company:
            return self.budget.company.id

    @fields.depends('budget', '_parent_budget.company')
    def on_change_with_currency(self, name=None):
        if self.budget and self.budget.company:
            return self.budget.company.currency.id

    @classmethod
    def get_total_amount(cls, records, name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        children = cls.__table__()

        amounts = defaultdict(Decimal)
        ids = [p.id for p in records]
        query = (table
            .join(children,
                condition=(children.left >= table.left)
                & (children.right <= table.right))
            .select(
                table.id,
                Sum(Coalesce(children.amount, 0)),
                group_by=table.id))

        for sub_ids in grouped_slice(ids):
            query.where = reduce_ids(table.id, sub_ids)
            cursor.execute(*query)
            amounts.update(cursor)

        for record in records:
            amount = amounts[record.id]
            # SQLite uses float for SUM
            if amount is not None and not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            if amount is not None:
                amounts[record.id] = record.currency.round(amount)
        return amounts

    @fields.depends('account', 'name')
    def on_change_with_current_name(self, name=None):
        if self.account:
            return self.account.rec_name
        else:
            return self.name

    @classmethod
    def search_current_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('account.rec_name',) + tuple(clause[1:]),
            ('name',) + tuple(clause[1:]),
            ]

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('left', 0)
        default.setdefault('right', 0)
        if 'budget' in default and 'children.budget' not in default:
            default['children.budget'] = default['budget']
        if 'amount' in default and 'children.amount' not in default:
            default['children.amount'] = default['amount']
        return super().copy(records, default=default)


class BudgetContext(ModelView):
    "Account Budget Context"
    __name__ = 'account.budget.context'

    budget = fields.Many2One('account.budget', "Budget", required=True)
    posted = fields.Boolean(
        "Posted",
        help="Only include posted moves.")
    periods = fields.Many2Many(
        'account.period', None, None, "Periods",
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear', -1)),
            ('type', '=', 'standard'),
            ])

    fiscalyear = fields.Function(
        fields.Many2One('account.fiscalyear', "Fiscal Year"),
        'on_change_with_fiscalyear')

    @classmethod
    def default_budget(cls):
        pool = Pool()
        Budget = pool.get('account.budget')
        FiscalYear = pool.get('account.fiscalyear')
        context = Transaction().context
        if 'budget' in context:
            return context.get('budget')
        fiscalyear_id = FiscalYear.find(
            context.get('company'), exception=False)
        budgets = Budget.search([
                ('fiscalyear', '=', fiscalyear_id),
                ], limit=1)
        if budgets:
            budget, = budgets
            return budget.id

    @fields.depends('budget')
    def on_change_with_fiscalyear(self, name=None):
        if self.budget:
            return self.budget.fiscalyear.id


class Budget(BudgetMixin, ModelSQL, ModelView):
    "Account Budget"
    __name__ = 'account.budget'

    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True,
        domain=[('company', '=', Eval('company', -1))],
        help="The fiscal year the budget applies to.")
    lines = fields.One2Many(
        'account.budget.line', 'budget', "Lines",
        states={
            'readonly': Eval('id', -1) < 0,
            },
        order=[('left', 'ASC'), ('id', 'ASC')])
    root_lines = fields.One2Many(
        'account.budget.line', 'budget', "Lines",
        states={
            'readonly': Eval('id', -1) < 0,
            },
        filter=[
            ('parent', '=', None),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('fiscalyear', 'DESC'))
        cls._buttons.update({
                'update_lines': {},
                'copy_button': {},
                })

    @classmethod
    def default_fiscalyear(cls):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        context = Transaction().context
        return FiscalYear.find(context.get('company'), exception=False)

    def get_rec_name(self, name):
        return '%s - %s' % (self.name, self.fiscalyear.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('name',) + tuple(clause[1:]),
            ('fiscalyear.rec_name',) + tuple(clause[1:]),
            ]

    def _account_type_domain(self):
        return [
            ('company', '=', self.company.id),
            ('statement', '=', 'income'),
            ]

    def _account_domain(self):
        return [
            ('company', '=', self.company.id),
            ('type', 'where', self._account_type_domain()),
            ('closed', '!=', True),
            ]

    @classmethod
    @ModelView.button
    def update_lines(cls, budgets):
        pool = Pool()
        Account = pool.get('account.account')
        AccountType = pool.get('account.account.type')
        Line = pool.get('account.budget.line')
        company_account_types = {}
        company_accounts = {}
        for budget in budgets:
            company = budget.company
            if company not in company_account_types:
                company_account_types[company] = set(
                    AccountType.search(budget._account_type_domain()))
            type_lines = Line.search([
                    ('budget', '=', budget.id),
                    ('account_type', '!=', None),
                    ])
            types2lines = {l.account_type: l for l in type_lines}
            lines = []
            for account_type in (
                    company_account_types[company] - set(types2lines.keys())):
                line = Line(
                    budget=budget,
                    account_type=account_type,
                    sequence=account_type.sequence)
                types2lines[account_type] = line
                lines.append(line)
            Line.save(lines)

            if company not in company_accounts:
                company_accounts[company] = set(
                    Account.search(budget._account_domain()))
            account_lines = Line.search([
                    ('budget', '=', budget.id),
                    ('account', '!=', None),
                    ])
            accounts = {l.account for l in account_lines}
            lines = []
            for account in sorted(
                    company_accounts[company] - accounts,
                    key=lambda a: a.code or ''):
                lines.append(Line(
                        budget=budget,
                        account=account,
                        parent=types2lines.get(account.type)))
            Line.save(lines)
            for account_type, line in types2lines.items():
                parent = types2lines.get(account_type.parent)
                if line.parent != parent:
                    line.parent = parent
            Line.save(types2lines.values())

    @classmethod
    @ModelView.button_action('account_budget.wizard_budget_copy')
    def copy_button(cls, budgets):
        pass


class BudgetLine(BudgetLineMixin, ModelSQL, ModelView):
    "Account Budget Line"
    __name__ = 'account.budget.line'

    budget = fields.Many2One(
        'account.budget', "Budget",
        required=True, select=True, ondelete='CASCADE')
    account_type = fields.Many2One(
        'account.account.type', "Account Type",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('statement', '=', 'income'),
            ],
        states={
            'required': ~Eval('name') & ~Eval('account'),
            'invisible': Eval('name') | Eval('account'),
            'readonly': Bool(Eval('lines', [-1])),
            },
        help="The account type the budget applies to.")
    account = fields.Many2One(
        'account.account', "Account",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('type.statement', '=', 'income'),
            ('closed', '!=', True),
            If(Eval('parent_account_type'),
                ('type', '=', Eval('parent_account_type', -1)),
                ()),
            ],
        states={
            'required': ~Eval('name') & ~Eval('account_type'),
            'invisible': Eval('name') | Eval('account_type'),
            },
        help="The account the budget applies to.")
    periods = fields.One2Many(
        'account.budget.line.period', 'budget_line', "Periods",
        order=[('period', 'ASC')],
        help="The periods that contain details of the budget.")

    parent_account_type = fields.Function(
        fields.Many2One('account.account.type', "Parent Account Type"),
        'on_change_with_parent_account_type')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.name.states['required'] &= ~Eval('account_type')
        cls.name.states['invisible'] |= Eval('account_type')
        cls.name.depends.add('account_type')
        t = cls.__table__()
        cls._sql_constraints.append(
            ('budget_account_unique', Unique(t, t.budget, t.account),
                'account_budget.msg_budget_line_budget_account_unique'))
        cls._buttons.update({
            'create_periods': {
                'invisible': Bool(Eval('periods', [1])),
                },
            })
        cls.__rpc__.update({
                'create_period': RPC(readonly=False, instantiate=0),
                })

    @fields.depends('parent', '_parent_parent.account_type')
    def on_change_with_parent_account_type(self, name=None):
        if self.parent and self.parent.account_type:
            return self.parent.account_type.id

    @fields.depends('account_type')
    def on_change_with_current_name(self, name=None):
        name = super().on_change_with_current_name(name)
        if self.account_type:
            name = self.account_type.name
        return name

    @classmethod
    def search_current_name(cls, name, clause):
        return super().search_rec_name(name, clause) + [
            ('account_type.name',) + tuple(clause[1:]),
            ]

    @classmethod
    def get_total_amount(cls, lines, name):
        amounts = super().get_total_amount(lines, name)
        periods = Transaction().context.get('periods')
        if periods:
            for line in lines:
                ratio = sum(
                    p.ratio for p in line.periods if p.period.id in periods)
                amounts[line.id] = line.currency.round(
                    amounts[line.id] * ratio)
        return amounts

    @classmethod
    def _get_amount_group_key(cls, record):
        return (('fiscalyear', record.budget.fiscalyear.id),)

    @classmethod
    def _get_amount_query(cls, records, context):
        pool = Pool()
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        table = cls.__table__()
        children = cls.__table__()
        line = Line.__table__()

        amount = Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0))
        red_sql = reduce_ids(table.id, [r.id for r in records])
        periods = Transaction().context.get('periods')
        if not periods:
            periods = [p.id for p in Period.search([
                        ('fiscalyear', '=', context.get('fiscalyear')),
                        ('type', '=', 'standard'),
                        ])]
        with Transaction().set_context(context, periods=periods):
            query_where, _ = Line.query_get(line)
        return (table
            .join(
                children,
                condition=(children.left >= table.left)
                & (children.right <= table.right))
            .join(
                line,
                condition=line.account == children.account)
            .select(
                table.id, amount,
                where=red_sql & query_where,
                group_by=table.id))

    @classmethod
    def copy(cls, lines, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('periods')
        return super().copy(lines, default=default)

    @classmethod
    @ModelView.button_action(
        'account_budget.wizard_budget_line_create_periods')
    def create_periods(cls, lines):
        pass

    def create_period(self, method_name, account_periods):
        pool = Pool()
        Period = pool.get('account.budget.line.period')
        method = getattr(self, 'distribute_%s' % method_name)
        periods = []
        if not self.periods:
            for account_period in account_periods:
                period = Period()
                period.budget_line = self
                period.period = account_period
                period.ratio = method(period, account_periods).quantize(
                    Decimal('0.0001'), ROUND_DOWN)
                periods.append(period)
        for child in self.children:
            periods.extend(child.create_period(method_name, account_periods))
        return periods

    def distribute_evenly(self, period, periods):
        return 1 / Decimal(len(periods))


class BudgetLinePeriod(AmountMixin, ModelSQL, ModelView):
    "Account Budget Line Period"
    __name__ = 'account.budget.line.period'

    budget_line = fields.Many2One(
        'account.budget.line', "Budget Line", required=True, select=True,
        ondelete="CASCADE",
        help="The line that the budget period is part of.")
    fiscalyear = fields.Function(
        fields.Many2One('account.fiscalyear', "Fiscal Year"),
        'on_change_with_fiscalyear')
    period = fields.Many2One(
        'account.period', "Period", required=True,
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear', -1)),
            ('type', '=', 'standard'),
            ])
    currency = fields.Function(
        fields.Many2One('currency.currency', "Currency"),
        'on_change_with_currency')

    ratio = fields.Numeric(
        "Ratio", digits=(1, 4),
        help="The percentage allocated to the budget.")
    total_amount = fields.Function(
        Monetary(
            "Total Amount", currency='currency', digits='currency',
            help="The total amount allocated to the budget and its children."),
        'get_total_amount')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints.append(
            ('budget_line_period_unique', Unique(t, t.budget_line, t.period),
                'account_budget'
                '.msg_budget_line_period_budget_line_period_unique'))
        cls.__access__.add('budget_line')
        cls._order.insert(0, ('period', 'DESC'))

    @fields.depends('budget_line', '_parent_budget_line.company')
    def on_change_with_currency(self, name=None):
        if self.budget_line and self.budget_line.company:
            return self.budget_line.company.currency.id

    @fields.depends(
        'budget_line',
        '_parent_budget_line.budget',
        '_parent_budget_line._parent_budget.fiscalyear')
    def on_change_with_fiscalyear(self, name=None):
        if (self.budget_line
                and self.budget_line.budget
                and self.budget_line.budget.fiscalyear):
            return self.budget_line.budget.fiscalyear.id

    @classmethod
    def get_total_amount(cls, periods, name):
        amounts = {}
        with Transaction().set_context(periods=None):
            periods = cls.browse(periods)
        for period in periods:
            if period.budget_line.total_amount is not None:
                amount = period.currency.round(
                    period.budget_line.total_amount * period.ratio)
            else:
                amount = None
            amounts[period.id] = amount
        return amounts

    @classmethod
    def _get_amount_group_key(cls, record):
        return (('fiscalyear', record.budget_line.budget.fiscalyear.id),)

    @classmethod
    def _get_amount_query(cls, records, context):
        pool = Pool()
        BudgetLine = pool.get('account.budget.line')
        Move = pool.get('account.move')
        MoveLine = pool.get('account.move.line')
        Period = pool.get('account.period')

        table = cls.__table__()
        budget_line = BudgetLine.__table__()
        children = BudgetLine.__table__()
        move = Move.__table__()
        line = MoveLine.__table__()

        amount = Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0))
        red_sql = reduce_ids(table.id, [r.id for r in records])
        periods = Transaction().context.get('periods')
        if not periods:
            periods = [p.id for p in Period.search([
                        ('fiscalyear', '=', context.get('fiscalyear')),
                        ('type', '=', 'standard'),
                        ])]

        with Transaction().set_context(context, periods=periods):
            query_where, _ = MoveLine.query_get(line)
        return (table
            .join(budget_line, condition=budget_line.id == table.budget_line)
            .join(
                children,
                condition=(children.left >= budget_line.left)
                & (children.right <= budget_line.right))
            .join(
                line,
                condition=line.account == children.account)
            .join(move,
                condition=(line.move == move.id)
                & (move.period == table.period))
            .select(
                table.id, amount,
                where=red_sql & query_where,
                group_by=table.id))

    @classmethod
    def validate_fields(cls, periods, field_names):
        super().validate_fields(periods, field_names)
        cls.check_ratio(periods, field_names)

    @classmethod
    def check_ratio(cls, periods, field_names=None):
        pool = Pool()
        Line = pool.get('account.budget.line')
        if field_names and not (field_names & {'ratio', 'budget_line'}):
            return
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        for sub_ids in grouped_slice({p.budget_line.id for p in periods}):
            cursor.execute(*table.select(
                    table.budget_line,
                    where=reduce_ids(table.budget_line, sub_ids),
                    group_by=table.budget_line,
                    having=Sum(table.ratio) > 1,
                    limit=1))
            try:
                line_id, = cursor.fetchone()
            except TypeError:
                continue
            line = Line(line_id)
            raise BudgetValidationError(
                gettext('account_budget.msg_budget_line_period_ratio',
                    budget_line=line.rec_name))


class CopyBudgetMixin:
    __slots__ = ()

    def default_start(self, field_names):
        return {
            'name': self.record.name,
            'company': self.record.company.id,
            }

    def _copy_default(self):
        default = {'name': self.start.name}
        factor = self.start.factor
        if factor != 1:
            currency = self.start.company.currency
            default['root_lines.amount'] = (
                lambda data: currency.round(data['amount'] * factor)
                if data['amount'] else data['amount'])
        return default

    def do_copy(self, action):
        record, = self.model.copy([self.record], default=self._copy_default())
        data = {'res_id': [record.id]}
        action['views'].reverse()
        return action, data


class CopyBudgetStartMixin:
    __slots__ = ()
    name = fields.Char("Name", required=True)
    factor = fields.Numeric(
        "Factor",
        help="The percentage to apply to the budget line amounts.")
    company = fields.Many2One('company.company', "Company", readonly=True)

    @classmethod
    def default_factor(cls):
        return Decimal(1)


class CopyBudget(CopyBudgetMixin, Wizard):
    "Copy Budget"
    __name__ = 'account.budget.copy'

    start = StateView('account.budget.copy.start',
        'account_budget.budget_copy_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Copy", 'copy', 'tryton-ok', default=True),
            ])
    copy = StateAction('account_budget.act_budget_form')

    def default_start(self, field_names):
        values = super().default_start(field_names)
        values['fiscalyear'] = self.record.fiscalyear.id
        return values

    def _copy_default(self):
        default = super()._copy_default()
        default['fiscalyear'] = self.start.fiscalyear.id
        return default


class CopyBudgetStart(CopyBudgetStartMixin, ModelView):
    "Copy Budget"
    __name__ = 'account.budget.copy.start'

    fiscalyear = fields.Many2One(
        'account.fiscalyear', "Fiscal Year", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        help="The fiscal year during which the new budget will apply.")


class CreatePeriods(Wizard):
    "Create Periods"
    __name__ = 'account.budget.line.create_periods'

    start = StateView('account.budget.line.create_periods.start',
        'account_budget.budget_create_periods_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Create", 'create_periods', 'tryton-ok', default=True),
            ])
    create_periods = StateTransition()

    def transition_create_periods(self):
        pool = Pool()
        AccountPeriod = pool.get('account.period')
        Period = pool.get('account.budget.line.period')
        account_periods = AccountPeriod.search([
                ('fiscalyear', '=', self.record.budget.fiscalyear.id),
                ('type', '=', 'standard'),
                ])
        periods = self.record.create_period(self.start.method, account_periods)
        Period.save(periods)
        return 'end'


class CreatePeriodsStart(ModelView):
    "Create Periods"
    __name__ = 'account.budget.line.create_periods.start'

    method = fields.Selection([
            ('evenly', "Evenly"),
            ], "Method", required=True)

    @classmethod
    def default_method(cls):
        return 'evenly'
