# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import tee, zip_longest

from dateutil.relativedelta import relativedelta

try:
    import pygal
except ImportError:
    pygal = None
from sql import Literal, Null
from sql.aggregate import Count, Min, Sum
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, DateTrunc

from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


def pairwise(iterable):
    a, b = tee(iterable)
    next(b)
    return zip_longest(a, b)


class Agent(ModelView, ModelSQL):
    "Commission Reporting per Agent"
    __name__ = 'commission.reporting.agent'

    agent = fields.Many2One('commission.agent', 'Agent')
    number = fields.Integer("Number")

    base_amount = Monetary(
        "Base Amount", currency='currency', digits='currency')
    base_amount_trend = fields.Function(
        fields.Char("Base Amount Trend"), 'get_trend')
    amount = Monetary("Amount", currency='currency', digits=price_digits)

    time_series = fields.One2Many(
        'commission.reporting.agent.time_series', 'agent', "Time Series")

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_currency')

    @classmethod
    def table_query(cls):
        from_item, tables, withs = cls._joins()
        return from_item.select(
            *cls._columns(tables, withs),
            where=cls._where(tables, withs),
            group_by=cls._group_by(tables, withs),
            with_=withs.values())

    @classmethod
    def _joins(cls):
        pool = Pool()
        Commission = pool.get('commission')
        Agent = pool.get('commission.agent')

        tables = {}
        tables['commission'] = commission = Commission.__table__()
        tables['commission.agent'] = agent = Agent.__table__()
        withs = {}

        from_item = (commission
            .join(agent, condition=commission.agent == agent.id))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        commission = tables['commission']
        return [
            cls._column_id(tables, withs).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            commission.agent.as_('agent'),
            Count(commission.id, distinct=True).as_('number'),
            Sum(Coalesce(commission.base_amount, 0)).as_('base_amount'),
            Sum(commission.amount).as_('amount'),
            ]

    @classmethod
    def _column_id(cls, tables, withs):
        commission = tables['commission']
        return commission.agent

    @classmethod
    def _group_by(cls, tables, withs):
        commission = tables['commission']
        return [commission.agent]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        commission = tables['commission']
        agent = tables['commission.agent']
        where = agent.type_ == cls._get_agent_type(context.get('type', 'out'))
        from_date = context.get('from_date')
        if from_date:
            where &= commission.date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= commission.date <= to_date
        if context.get('invoiced'):
            where &= commission.invoice_line != Null
        return where

    @classmethod
    def _get_agent_type(cls, type):
        return {
            'out': 'agent',
            'in': 'principal',
            }.get(type)

    @property
    def time_series_all(self):
        delta = self._period_delta()
        for ts, next_ts in pairwise(self.time_series or []):
            yield ts
            if delta and next_ts:
                date = ts.date + delta
                while date < next_ts.date:
                    yield None
                    date += delta

    @classmethod
    def _period_delta(cls):
        context = Transaction().context
        return {
            'year': relativedelta(years=1),
            'month': relativedelta(months=1),
            'day': relativedelta(days=1),
            }.get(context.get('period'))

    def get_trend(self, name):
        name = name[:-len('_trend')]
        if pygal:
            chart = pygal.Line()
            chart.add('', [
                    getattr(ts, name, 0) or 0
                    for ts in self.time_series_all])
            return chart.render_sparktext()

    def get_currency(self, name):
        return self.agent.currency.id


class AgentTimeseries(Agent):
    "Commission Reporting per Agent"
    __name__ = 'commission.reporting.agent.time_series'

    date = fields.Date("Date")
    time_series = None

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('date', 'ASC')]

    @classmethod
    def _columns(cls, tables, withs):
        return super()._columns(tables, withs) + [
            cls._column_date(tables, withs).as_('date')]

    @classmethod
    def _column_id(cls, tables, withs):
        commission = tables['commission']
        return Min(commission.id)

    @classmethod
    def _column_date(cls, tables, withs):
        context = Transaction().context
        commission = tables['commission']
        date = DateTrunc(context.get('period'), commission.date)
        date = cls.date.sql_cast(date)
        return date

    @classmethod
    def _group_by(cls, tables, withs):
        return super()._group_by(tables, withs) + [
            cls._column_date(tables, withs)]


class Context(ModelView):
    "Commission Reporting Context"
    __name__ = 'commission.reporting.context'

    type = fields.Selection([
            ('in', "Incoming"),
            ('out', "Outgoing"),
            ], "Type", required=True)
    from_date = fields.Date("From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ])
    to_date = fields.Date("To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ])
    period = fields.Selection([
            ('year', "Year"),
            ('month', "Month"),
            ('day', "Day"),
            ], "Period", required=True)
    invoiced = fields.Boolean(
        "Invoiced",
        help="Only include invoiced commissions.")

    @classmethod
    def default_type(cls):
        return Transaction().context.get('type', 'out')

    @classmethod
    def default_from_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'from_date' in context:
            return context['from_date']
        return Date.today() - relativedelta(years=1)

    @classmethod
    def default_to_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'to_date' in context:
            return context['to_date']
        return Date.today()

    @classmethod
    def default_period(cls):
        return Transaction().context.get('period', 'month')
