# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import ModelSQL, ModelView, Unique, fields
from trytond.modules.account_budget import (
    BudgetLineMixin, BudgetMixin, CopyBudgetMixin, CopyBudgetStartMixin)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools import reduce_ids
from trytond.transaction import Transaction
from trytond.wizard import Button, StateAction, StateView, Wizard


class BudgetContext(ModelView):
    "Analytic Budget Context"
    __name__ = 'analytic_account.budget.context'

    budget = fields.Many2One(
        'analytic_account.budget', "Budget", required=True)

    @classmethod
    def default_budget(cls):
        pool = Pool()
        Budget = pool.get('analytic_account.budget')
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'budget' in context:
            return context.get('budget')
        today = Date.today()
        budgets = Budget.search([
                ('start_date', '>=', today),
                ('end_date', '<=', today),
                ], limit=1)
        if budgets:
            budget, = budgets
            return budget.id


class Budget(BudgetMixin, ModelSQL, ModelView):
    "Analytic Budget"
    __name__ = 'analytic_account.budget'

    start_date = fields.Date(
        "Start Date", required=True,
        domain=[('start_date', '<=', Eval('end_date'))])
    end_date = fields.Date(
        "End Date", required=True,
        domain=[('end_date', '>=', Eval('start_date'))])
    root = fields.Many2One(
        'analytic_account.account', "Root", required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('parent', '=', None),
            ('type', '=', 'root'),
            ],
        states={
            'readonly': Eval('root') & Eval('lines', [-1]),
            })
    lines = fields.One2Many(
        'analytic_account.budget.line', 'budget', "Lines",
        states={
            'readonly': Eval('id', -1) < 0,
            },
        order=[('left', 'ASC'), ('id', 'ASC')])
    root_lines = fields.One2Many(
        'analytic_account.budget.line', 'budget', "Lines",
        states={
            'readonly': Eval('id', -1) < 0,
            },
        filter=[
            ('parent', '=', None),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('start_date', 'DESC'))
        cls._buttons.update({
                'update_lines': {},
                'copy_button': {},
                })

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return '%s (%s - %s)' % (
            self.name,
            lang.strftime(self.start_date),
            lang.strftime(self.end_date))

    def _account_domain(self):
        return [
            ('company', '=', self.company.id),
            ('root', '=', self.root.id),
            ('type', '=', 'normal'),
            ]

    @classmethod
    @ModelView.button
    def update_lines(cls, budgets):
        pool = Pool()
        Account = pool.get('analytic_account.account')
        Line = pool.get('analytic_account.budget.line')
        company_accounts = {}
        for budget in budgets:
            company = budget.company
            if company not in company_accounts:
                company_accounts[company] = set(
                    Account.search(budget._account_domain()))
            lines = Line.search([
                    ('budget', '=', budget.id),
                    ('account', '!=', None),
                    ])
            accounts2lines = {l.account: l for l in lines}
            lines = []
            for account in sorted(
                    company_accounts[company] - set(accounts2lines.keys()),
                    key=lambda a: (a.code or '', a.name)):
                lines.append(Line(budget=budget, account=account))
            Line.save(lines)

            for account, line in accounts2lines.items():
                parent = accounts2lines.get(line.account.parent)
                if line.parent != parent:
                    line.parent = parent
            Line.save(accounts2lines.values())

    @classmethod
    @ModelView.button_action('analytic_budget.wizard_budget_copy')
    def copy_button(cls, budgets):
        pass


class BudgetLine(BudgetLineMixin, ModelSQL, ModelView):
    "Analytic Budget"
    __name__ = 'analytic_account.budget.line'

    budget = fields.Many2One(
        'analytic_account.budget', "Budget",
        required=True, select=True, ondelete='CASCADE')
    account = fields.Many2One(
        'analytic_account.account', "Account",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('root', '=', Eval('root', -1)),
            ('type', '=', 'normal'),
            ])

    root = fields.Function(fields.Many2One(
            'analytic_account.account', "Root"),
        'on_change_with_root')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints.append(
            ('budget_account_unique', Unique(t, t.budget, t.account),
                'analytic_account.msg_budget_line_budget_account_unique'))
        cls.__access__.add('budget')

    @fields.depends('budget', '_parent_budget.root')
    def on_change_with_root(self, name=None):
        if self.budget and self.budget.root:
            return self.budget.root.id

    @classmethod
    def _get_amount_group_key(cls, record):
        return (
            ('start_date', record.budget.start_date),
            ('end_date', record.budget.end_date),
            )

    @classmethod
    def _get_amount_query(cls, records, context):
        pool = Pool()
        Line = pool.get('analytic_account.line')

        line = Line.__table__()
        table = cls.__table__()
        children = cls.__table__()

        balance = Sum(Coalesce(line.debit, 0) - Coalesce(line.credit, 0))
        red_sql = reduce_ids(table.id, [r.id for r in records])
        with Transaction().set_context(context):
            query_where = Line.query_get(line)
        return (table
            .join(
                children,
                condition=(children.left >= table.left)
                & (children.right <= table.right))
            .join(
                line,
                condition=line.account == children.account)
            .select(
                table.id, balance,
                where=red_sql & query_where,
                group_by=table.id))


class CopyBudget(CopyBudgetMixin, Wizard):
    "Copy Analytic Budget"
    __name__ = 'analytic_account.budget.copy'

    start = StateView('analytic_account.budget.copy.start',
        'analytic_budget.budget_copy_start_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Copy", 'copy', 'tryton-ok', default=True),
            ])
    copy = StateAction('analytic_budget.act_budget_form')

    def default_start(self, field_names):
        values = super().default_start(field_names)
        values['start_date'] = self.record.start_date
        values['end_date'] = self.record.end_date
        return values

    def _copy_default(self):
        default = super()._copy_default()
        default['start_date'] = self.start.start_date
        default['end_date'] = self.start.end_date
        return default


class CopyBudgetStart(CopyBudgetStartMixin, ModelView):
    "Copy Analytic Budget"
    __name__ = 'analytic_account.budget.copy.start'

    start_date = fields.Date(
        "Start Date", required=True,
        domain=[('start_date', '<=', Eval('end_date'))])
    end_date = fields.Date(
        "End Date", required=True,
        domain=[('end_date', '>=', Eval('start_date'))])
