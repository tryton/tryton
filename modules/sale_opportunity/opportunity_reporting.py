# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from dateutil.relativedelta import relativedelta
from sql import Literal, Null, With
from sql.aggregate import Count, Min, Sum
from sql.conditionals import Case
from sql.functions import CurrentTimestamp

from trytond.i18n import lazy_gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.tools import pairwise_longest
from trytond.tools.chart import sparkline
from trytond.transaction import Transaction


class Abstract(ModelSQL):

    company = fields.Many2One(
        'company.company', lazy_gettext('sale.msg_sale_reporting_company'))

    number = fields.Integer(lazy_gettext('sale.msg_sale_reporting_number'),
        help=lazy_gettext(
            'sale_opportunity.msg_sale_opportunity_reporting_number_help'))
    number_trend = fields.Function(
        fields.Char(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_number_trend')),
        'get_trend')

    amount = Monetary(
        lazy_gettext('sale_opportunity.msg_sale_opportunity_reporting_amount'),
        currency='currency', digits='currency')
    amount_trend = fields.Function(
        fields.Char(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_amount_trend')),
        'get_trend')

    converted = fields.Integer(
        lazy_gettext(
            'sale_opportunity.msg_sale_opportunity_reporting_converted'))
    conversion_rate = fields.Function(
        fields.Float(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_conversion_rate'),
            digits=(1, 4)), 'get_rate')
    conversion_trend = fields.Function(
        fields.Char(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_conversion_trend')),
        'get_trend')
    converted_amount = Monetary(
        lazy_gettext(
            'sale_opportunity.'
            'msg_sale_opportunity_reporting_converted_amount'),
        currency='currency', digits='currency')
    converted_amount_trend = fields.Function(
        fields.Char(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_converted_amount_trend')),
        'get_trend')

    time_series = None

    currency = fields.Function(
        fields.Many2One(
            'currency.currency',
            lazy_gettext('sale.msg_sale_reporting_currency')),
        'get_currency')

    @classmethod
    def table_query(cls):
        from_item, tables, withs = cls._joins()
        return from_item.select(*cls._columns(tables, withs),
            where=cls._where(tables, withs),
            group_by=cls._group_by(tables, withs),
            with_=withs.values())

    @classmethod
    def _joins(cls):
        pool = Pool()
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Opportunity = pool.get('sale.opportunity')
        context = Transaction().context

        tables = {}
        company = context.get('company')
        tables['opportunity'] = opportunity = Opportunity.__table__()
        tables['opportunity.company'] = company = Company.__table__()
        withs = {}
        currency_opportunity = With(query=Currency.currency_rate_sql())
        withs['currency_opportunity'] = currency_opportunity
        currency_company = With(query=Currency.currency_rate_sql())
        withs['currency_company'] = currency_company

        from_item = (opportunity
            .join(currency_opportunity,
                condition=(
                    opportunity.currency == currency_opportunity.currency)
                & (currency_opportunity.start_date <= opportunity.start_date)
                & ((currency_opportunity.end_date == Null)
                    | (currency_opportunity.end_date > opportunity.start_date))
                )
            .join(company, condition=opportunity.company == company.id)
            .join(currency_company,
                condition=(company.currency == currency_company.currency)
                & (currency_company.start_date <= opportunity.start_date)
                & ((currency_company.end_date == Null)
                    | (currency_company.end_date > opportunity.start_date))
                ))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        opportunity = tables['opportunity']
        return [
            cls._column_id(tables, withs).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            opportunity.company.as_('company'),
            Count(Literal(1)).as_('number'),
            Sum(opportunity.amount).as_('amount'),
            Sum(Case(
                    (opportunity.state.in_(cls._converted_states()),
                        Literal(1)), else_=Literal(0))).as_('converted'),
            Sum(Case(
                    (opportunity.state.in_(cls._converted_states()),
                        opportunity.amount),
                    else_=Literal(0))).as_('converted_amount'),
            ]

    @classmethod
    def _column_id(cls, tables, withs):
        opportunity = tables['opportunity']
        return Min(opportunity.id)

    @classmethod
    def _group_by(cls, tables, withs):
        opportunity = tables['opportunity']
        return [opportunity.company]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        opportunity = tables['opportunity']

        where = opportunity.company == context.get('company')

        date = cls._column_date(tables, withs)
        from_date = context.get('from_date')
        if from_date:
            where &= date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= date <= to_date
        return where

    @classmethod
    def _column_date(cls, tables, withs):
        opportunity = tables['opportunity']
        return opportunity.start_date

    @classmethod
    def _converted_states(cls):
        return ['converted', 'won']

    @classmethod
    def _field_name_strip(cls, name, suffix):
        name = name[:-len(suffix)]
        return (name
            .replace('conversion', 'converted')
            .replace('winning', 'won'))

    def get_rate(self, name):
        if self.number:
            digits = getattr(self.__class__, name).digits[1]
            name = self._field_name_strip(name, '_rate')
            value = float(getattr(self, name))
            return round(value / self.number, digits)
        else:
            return 0.0

    @property
    def time_series_all(self):
        delta = self._period_delta()
        for ts, next_ts in pairwise_longest(self.time_series or []):
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
        name = self._field_name_strip(name, '_trend')
        return sparkline(
            [getattr(ts, name) or 0 if ts else 0
                for ts in self.time_series_all])

    def get_currency(self, name):
        return self.company.currency.id


class AbstractTimeseries(Abstract):

    date = fields.Date(lazy_gettext('sale.msg_sale_reporting_date'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('date', 'ASC')]

    @classmethod
    def _columns(cls, tables, withs):
        return super()._columns(tables, withs) + [
            cls._column_date(tables, withs).as_('date')]

    @classmethod
    def _group_by(cls, tables, withs):
        return super()._group_by(tables, withs) + [
            cls._column_date(tables, withs)]


class AbstractConversion(Abstract):

    won = fields.Integer(
        lazy_gettext('sale_opportunity.msg_sale_opportunity_reporting_won'))
    winning_rate = fields.Function(
        fields.Float(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_winning_rate'),
            digits=(1, 4)),
        'get_rate')
    winning_trend = fields.Function(
        fields.Char(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_winning_trend')),
        'get_trend')
    won_amount = Monetary(
        lazy_gettext(
            'sale_opportunity.msg_sale_opportunity_reporting_won_amount'),
        currency='currency', digits='currency')
    won_amount_trend = fields.Function(
        fields.Char(lazy_gettext(
                'sale_opportunity.'
                'msg_sale_opportunity_reporting_won_amount_trend')),
        'get_trend')

    lost = fields.Integer(
        lazy_gettext('sale_opportunity.msg_sale_opportunity_reporting_lost'))

    @classmethod
    def _columns(cls, tables, withs):
        opportunity = tables['opportunity']
        return super()._columns(tables, withs) + [
            Sum(Case(
                    (opportunity.state.in_(cls._won_states()),
                        Literal(1)), else_=Literal(0))).as_('won'),
            Sum(Case(
                    (opportunity.state.in_(cls._won_states()),
                        opportunity.amount),
                    else_=Literal(0))).as_('won_amount'),
            Sum(Case(
                    (opportunity.state.in_(cls._lost_states()),
                        Literal(1)), else_=Literal(0))).as_('lost'),
            ]

    @classmethod
    def _column_date(cls, tables, withs):
        opportunity = tables['opportunity']
        return opportunity.end_date

    @classmethod
    def _won_states(cls):
        return ['won']

    @classmethod
    def _lost_states(cls):
        return ['lost']

    @classmethod
    def _opportunity_states(cls):
        return cls._converted_states() + cls._won_states() + cls._lost_states()


class AbstractConversionTimeseries(AbstractConversion, AbstractTimeseries):
    pass


class Context(ModelView):
    "Sale Opportunity Reporting Context"
    __name__ = 'sale.opportunity.reporting.context'

    company = fields.Many2One('company.company', "Company", required=True)
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

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

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


class Main(Abstract, ModelView):
    "Sale Opportunity Reporting"
    __name__ = 'sale.opportunity.reporting.main'

    time_series = fields.Function(fields.One2Many(
            'sale.opportunity.reporting.main.time_series', None,
            lazy_gettext('sale.msg_sale_reporting_time_series')),
        'get_time_series')

    def get_rec_name(self, name):
        return ''

    def get_time_series(self, name):
        pool = Pool()
        Timeseries = pool.get('sale.opportunity.reporting.main.time_series')
        return [t.id for t in Timeseries.search([])]


class MainTimeseries(AbstractTimeseries, ModelView):
    "Sale Opportunity Reporting"
    __name__ = 'sale.opportunity.reporting.main.time_series'


class Conversion(AbstractConversion, ModelView):
    "Sale Opportunity Reporting Conversion"
    __name__ = 'sale.opportunity.reporting.conversion'

    time_series = fields.Function(fields.One2Many(
            'sale.opportunity.reporting.conversion.time_series', None,
            lazy_gettext('sale.msg_sale_reporting_time_series')),
        'get_time_series')

    def get_rec_name(self, name):
        return ''

    def get_time_series(self, name):
        pool = Pool()
        Timeseries = pool.get(
            'sale.opportunity.reporting.conversion.time_series')
        return [t.id for t in Timeseries.search([])]


class ConversionTimeseries(AbstractConversionTimeseries, ModelView):
    "Sale Opportunity Reporting Conversion"
    __name__ = 'sale.opportunity.reporting.conversion.time_series'


class EmployeeMixin:
    __slots__ = ()

    employee = fields.Many2One('company.employee', "Employee")

    @classmethod
    def _columns(cls, tables, withs):
        opportunity = tables['opportunity']
        return super()._columns(tables, withs) + [
            opportunity.employee.as_('employee')]

    @classmethod
    def _group_by(cls, tables, withs):
        opportunity = tables['opportunity']
        return super()._group_by(tables, withs) + [
            opportunity.employee]

    def get_rec_name(self, name):
        if self.employee:
            return self.employee.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('employee.rec_name', *clause[1:])]


class ConversionEmployee(EmployeeMixin, AbstractConversion, ModelView):
    "Sale Opportunity Reporting Conversion per Employee"
    __name__ = 'sale.opportunity.reporting.conversion.employee'

    time_series = fields.One2Many(
        'sale.opportunity.reporting.conversion.employee.time_series',
        'employee', lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('employee', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        opportunity = tables['opportunity']
        return opportunity.employee

    @classmethod
    def _where(cls, tables, withs):
        opportunity = tables['opportunity']
        where = super()._where(tables, withs)
        where &= opportunity.employee != Null
        return where


class ConversionEmployeeTimeseries(
        EmployeeMixin, AbstractConversionTimeseries, ModelView):
    "Sale Opportunity Reporting Conversion per Employee"
    __name__ = 'sale.opportunity.reporting.conversion.employee.time_series'
