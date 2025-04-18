# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import As, Literal, Null, Select, Window
from sql.aggregate import BoolAnd, BoolOr, Min, Sum
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, FirstValue

from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.account import MoveLineMixin
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.transaction import Transaction


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    grouped_lines = fields.One2Many(
        'account.move.line.group', 'move', "Grouped Lines", readonly=True,
        states={
            'invisible': ~Eval('grouped_lines', []),
            })


class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'

    @classmethod
    def _view_reconciliation_muted(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        muted = super()._view_reconciliation_muted()
        muted.add(ModelData.get_id(
                'account_move_line_grouping',
                'move_line_group_view_list_move'))
        return muted


class MoveLineGroup(MoveLineMixin, ModelSQL, ModelView):
    "Account Move Line Group"
    __name__ = 'account.move.line.group'

    move = fields.Many2One('account.move', "Move", readonly=True)
    account = fields.Many2One(
        'account.account', "Account", readonly=True,
        context={
            'company': Eval('company', -1),
            'period': Eval('period', -1),
            },
        depends={'company', 'period'})
    party = fields.Many2One(
        'party.party', "Party", readonly=True,
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    maturity_date = fields.Date("Maturity Date", readonly=True)

    debit = Monetary(
        "Debit", currency='currency', digits='currency', readonly=True)
    credit = Monetary(
        "Credit", currency='currency', digits='currency', readonly=True)
    amount_second_currency = Monetary(
        "Amount Second Currency",
        currency='second_currency', digits='second_currency', readonly=True)
    second_currency = fields.Many2One(
        'currency.currency', "Second Currency", readonly=True)
    amount = fields.Function(Monetary(
            "Amount", currency='amount_currency', digits='amount_currency'),
        'get_amount')
    amount_currency = fields.Function(fields.Many2One(
            'currency.currency', "Amount Currency"), 'get_amount_currency')
    delegated_amount = fields.Function(Monetary(
            "Delegated Amount",
            currency='amount_currency', digits='amount_currency',
            states={
                'invisible': ~Eval('partially_reconciled', False),
                }),
        'get_delegated_amount')
    payable_receivable_balance = fields.Function(
        Monetary(
            "Payable/Receivable Balance",
            currency='amount_currency', digits='amount_currency'),
        'get_payable_receivable_balance')

    partially_reconciled = fields.Boolean(
        "Partially Reconciled", readonly=True)
    reconciled = fields.Boolean("Reconciled", readonly=True)
    amount_reconciled = Monetary(
        "Amount Reconciled",
        currency='currency', digits='currency', readonly=True)
    state = fields.Selection('get_states', "State", readonly=True, sort=False)

    company = fields.Function(
        fields.Many2One('company.company', "Company"),
        'get_move_field', searcher='search_move_field')
    journal = fields.Function(fields.Many2One(
            'account.journal', "Journal",
            context={
                'company': Eval('company', -1),
                },
            depends={'company'}),
        'get_move_field', searcher='search_move_field')
    period = fields.Function(fields.Many2One(
            'account.period', "Period"),
        'get_move_field', searcher='search_move_field')
    date = fields.Function(fields.Date(
            "Effective Date"),
        'get_move_field', searcher='search_move_field')
    move_origin = fields.Function(fields.Reference(
            "Move Origin", selection='get_move_origin'),
        'get_move_field', searcher='search_move_field')
    move_description_used = fields.Function(
        fields.Char("Move Description"),
        'get_move_field', searcher='search_move_field')
    move_state = fields.Function(fields.Selection(
            'get_move_states', "Move State"),
        'get_move_field', searcher='search_move_field')

    lines = fields.Many2Many(
        'account.move.line.group-move.line', 'group', 'line', "Lines",
        readonly=True)

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'on_change_with_currency')

    order_company = MoveLineMixin._order_move_field('company')
    order_period = MoveLineMixin._order_move_field('period')
    order_company = MoveLineMixin._order_move_field('company')
    order_date = MoveLineMixin._order_move_field('date')
    order_move_origin = MoveLineMixin._order_move_field('origin')
    order_move_state = MoveLineMixin._order_move_field('state')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('move')
        cls._order[0] = ('id', 'DESC')

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()

        std_columns = [
            Min(line.id).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            Literal(None).as_('write_uid'),
            Literal(None).as_('write_date'),
            ]
        grouped_columns = cls._grouped_columns(line)
        aggregated_columns = cls._aggregated_columns(line)

        columns = std_columns + grouped_columns + aggregated_columns
        grouped_columns = [
            c.expression if isinstance(c, As) else c for c in grouped_columns]
        return line.select(*columns, group_by=grouped_columns)

    @classmethod
    def _grouped_columns(cls, line):
        return [
            line.move,
            line.account,
            line.party,
            line.maturity_date,
            line.second_currency,
            line.state,
            ]

    @classmethod
    def _aggregated_columns(cls, line):
        context = Transaction().context
        if not context.get('reconciled', True):
            filter_ = line.reconciliation == Null
        else:
            filter_ = None
        return [
            Coalesce(Sum(line.debit, filter_=filter_), 0).as_('debit'),
            Coalesce(Sum(line.credit, filter_=filter_), 0).as_('credit'),
            Sum(line.amount_second_currency, filter_=filter_).as_(
                'amount_second_currency'),
            BoolOr(line.reconciliation != Null).as_('partially_reconciled'),
            BoolAnd(line.reconciliation != Null).as_('reconciled'),
            Sum(
                line.debit + line.credit,
                filter_=line.reconciliation != Null).as_('amount_reconciled'),
            ]

    @classmethod
    def get_states(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        return Line.fields_get(['state'])['state']['selection']

    @fields.depends('account')
    def on_change_with_currency(self, name=None):
        return self.account.currency if self.account else None

    def get_delegated_amount(self, name):
        return self.amount_currency.round(
            sum(l.delegated_amount for l in self.lines if l.delegated_amount))

    @classmethod
    def view_attributes(cls):
        attributes = super().view_attributes()
        view_ids = cls._view_reconciliation_muted()
        if Transaction().context.get('view_id') in view_ids:
            attributes.append(
                ('/tree', 'visual',
                    If(Bool(Eval('reconciliation')), 'muted', '')))
        return attributes

    @classmethod
    def _view_reconciliation_muted(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        return {ModelData.get_id(
                'account_move_line_grouping',
                'move_line_group_view_list_payable_receivable')}


class MoveLineGroup_MoveLine(ModelSQL):
    "Account Move Line Group - Move Line"
    __name__ = 'account.move.line.group-move.line'

    group = fields.Many2One('account.move.line.group', "Group")
    line = fields.Many2One('account.move.line', "Line")

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('account.move.line')
        LineGroup = pool.get('account.move.line.group')
        transaction = Transaction()
        database = transaction.database
        line = Line.__table__()

        std_columns = [
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            Literal(None).as_('write_uid'),
            Literal(None).as_('write_date'),
            ]

        if database.has_window_functions():
            grouped_columns = LineGroup._grouped_columns(line)
            window = Window(
                grouped_columns,
                order_by=[line.id.asc])
            query = line.select(
                line.id.as_('id'),
                FirstValue(line.id, window=window).as_('group'),
                line.id.as_('line'),
                *std_columns)
        else:
            query = Select(
                Null.as_('id'),
                Null.as_('group'),
                Null.as_('line'),
                *std_columns,
                limit=0)
        return query


class OpenAccount(metaclass=PoolMeta):
    __name__ = 'account.move.open_account'

    def do_open_(self, action):
        pool = Pool()
        Action = pool.get('ir.action')
        ModelData = pool.get('ir.model.data')
        context = Transaction().context
        if context.get('action_id') == ModelData.get_id(
                'account_move_line_grouping', 'act_open_account'):
            action_id = Action.get_action_id(
                ModelData.get_id(
                    'account_move_line_grouping', 'act_move_line_group_form'))
            action = Action(action_id).get_action_value()
        action, data = super().do_open_(action)
        return action, data
