# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    import pygal
except ImportError:
    pygal = None
from dateutil.relativedelta import relativedelta
from sql import Literal, Null
from sql.aggregate import Count, Min, Sum
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, DateTrunc

from trytond.i18n import lazy_gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.tools import pairwise_longest
from trytond.transaction import Transaction


class Abstract(ModelSQL):

    company = fields.Many2One(
        'company.company',
        lazy_gettext("purchase.msg_purchase_reporting_company"))
    number = fields.Integer(
        lazy_gettext("purchase.msg_purchase_reporting_number"),
        help=lazy_gettext("purchase.msg_purchase_reporting_number_help"))
    expense = Monetary(
        lazy_gettext("purchase.msg_purchase_reporting_expense"),
        digits='currency', currency='currency')
    expense_trend = fields.Function(
        fields.Char(
            lazy_gettext("purchase.msg_purchase_reporting_expense_trend")),
        'get_trend')
    time_series = None
    currency = fields.Many2One(
        'currency.currency',
        lazy_gettext("purchase.msg_purchase_reporting_currency"))

    @classmethod
    def table_query(cls):
        from_item, tables = cls._joins()
        return from_item.select(*cls._columns(tables),
            where=cls._where(tables),
            group_by=cls._group_by(tables))

    @classmethod
    def _joins(cls):
        pool = Pool()
        Line = pool.get('purchase.line')
        Purchase = pool.get('purchase.purchase')

        tables = {}
        tables['line'] = line = Line.__table__()
        tables['line.purchase'] = purchase = Purchase.__table__()

        from_item = (line
            .join(purchase, condition=line.purchase == purchase.id))
        return from_item, tables

    @classmethod
    def _columns(cls, tables):
        line = tables['line']
        purchase = tables['line.purchase']

        quantity = Coalesce(line.actual_quantity, line.quantity)
        expense = cls.expense.sql_cast(
            Sum(quantity * line.unit_price))
        return [
            cls._column_id(tables).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            purchase.company.as_('company'),
            purchase.currency.as_('currency'),
            expense.as_('expense'),
            Count(purchase.id, distinct=True).as_('number'),
            ]

    @classmethod
    def _column_id(cls, tables):
        line = tables['line']
        return Min(line.id)

    @classmethod
    def _group_by(cls, tables):
        purchase = tables['line.purchase']
        return [purchase.company, purchase.currency]

    @classmethod
    def _where(cls, tables):
        context = Transaction().context
        purchase = tables['line.purchase']

        where = purchase.company == context.get('company')
        where &= purchase.state.in_(cls._purchase_states())
        from_date = context.get('from_date')
        if from_date:
            where &= purchase.purchase_date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= purchase.purchase_date <= to_date
        warehouse = context.get('warehouse')
        if warehouse:
            where &= purchase.warehouse == warehouse
        return where

    @classmethod
    def _purchase_states(cls):
        return ['confirmed', 'processing', 'done']

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
        name = name[:-len('_trend')]
        if pygal:
            chart = pygal.Line()
            chart.add('', [getattr(ts, name) if ts else 0
                    for ts in self.time_series_all])
            return chart.render_sparktext()


class AbstractTimeseries(Abstract):

    date = fields.Date(lazy_gettext('purchase.msg_purchase_reporting_date'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('date', 'ASC')]

    @classmethod
    def _columns(cls, tables):
        return super()._columns(tables) + [
            cls._column_date(tables).as_('date')]

    @classmethod
    def _column_date(cls, tables):
        context = Transaction().context
        purchase = tables['line.purchase']
        date = DateTrunc(context.get('period'), purchase.purchase_date)
        date = cls.date.sql_cast(date)
        return date

    @classmethod
    def _group_by(cls, tables):
        return super()._group_by(tables) + [cls._column_date(tables)]


class Context(ModelView):
    "Purchase Reporting Context"
    __name__ = 'purchase.reporting.context'

    company = fields.Many2One('company.company', "Company", required=True)
    from_date = fields.Date("From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        depends=['to_date'])
    to_date = fields.Date("To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        depends=['from_date'])
    period = fields.Selection([
            ('year', "Year"),
            ('month', "Month"),
            ('day', "Day"),
            ], "Period", required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse",
        domain=[
            ('type', '=', 'warehouse'),
            ])

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

    @classmethod
    def default_warehouse(cls):
        return Transaction().context.get('warehouse')


class Main(Abstract, ModelView):
    "Purchase Reporting"
    __name__ = 'purchase.reporting.main'

    time_series = fields.Function(fields.One2Many(
            'purchase.reporting.main.time_series', None,
            lazy_gettext('purchase.msg_purchase_reporting_time_series')),
        'get_time_series')

    def get_rec_name(self, name):
        return ''

    def get_time_series(self, name):
        pool = Pool()
        Timeseries = pool.get('purchase.reporting.main.time_series')
        return [t.id for t in Timeseries.search([])]


class MainTimeseries(AbstractTimeseries, ModelView):
    "Purchase Reporting"
    __name__ = 'purchase.reporting.main.time_series'


class SupplierMixin(object):
    __slots__ = ()
    supplier = fields.Many2One(
        'party.party', "Supplier",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])

    @classmethod
    def _columns(cls, tables):
        purchase = tables['line.purchase']
        return super()._columns(tables) + [purchase.party.as_('supplier')]

    @classmethod
    def _group_by(cls, tables):
        purchase = tables['line.purchase']
        return super()._group_by(tables) + [purchase.party]

    def get_rec_name(self, name):
        return self.supplier.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('supplier.rec_name', *clause[1:])]


class Supplier(SupplierMixin, Abstract, ModelView):
    "Purchase Reporting per Supplier"
    __name__ = 'purchase.reporting.supplier'

    time_series = fields.One2Many(
        'purchase.reporting.supplier.time_series', 'supplier',
        lazy_gettext('purchase.msg_purchase_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('supplier', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        purchase = tables['line.purchase']
        return purchase.party


class SupplierTimeseries(SupplierMixin, AbstractTimeseries, ModelView):
    "Purchase Reporting per Supplier"
    __name__ = 'purchase.reporting.supplier.time_series'


class ProductMixin(object):
    __slots__ = ()
    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    product_supplier = fields.Many2One(
        'purchase.product_supplier', "Supplier's Product")

    @classmethod
    def _columns(cls, tables):
        line = tables['line']
        return super()._columns(tables) + [
            line.product.as_('product'),
            line.product_supplier.as_('product_supplier'),
            ]

    @classmethod
    def _group_by(cls, tables):
        line = tables['line']
        return super()._group_by(tables) + [
            line.product, line.product_supplier]

    @classmethod
    def _where(cls, tables):
        context = Transaction().context
        line = tables['line']
        purchase = tables['line.purchase']
        where = super()._where(tables)
        where &= line.product != Null
        where &= purchase.party == context.get('supplier')
        return where

    def get_rec_name(self, name):
        pool = Pool()
        Party = pool.get('party.party')
        context = Transaction().context

        name = self.product.rec_name if self.product else None
        if context.get('supplier'):
            supplier = Party(context['supplier'])
            name += '@%s' % supplier.rec_name
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name', *clause[1:])]


class Product(ProductMixin, Abstract, ModelView):
    "Purchase Reporting per Product"
    __name__ = 'purchase.reporting.product'

    time_series = fields.One2Many(
        'purchase.reporting.product.time_series', 'product',
        lazy_gettext('purchase.msg_purchase_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        line = tables['line']
        return line.product


class ProductTimeseries(ProductMixin, AbstractTimeseries, ModelView):
    "Purchase Reporting per Product"
    __name__ = 'purchase.reporting.product.time_series'
