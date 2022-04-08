# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from itertools import tee, zip_longest

from sql import Literal, Null, With
from sql.aggregate import Max, Min, Sum
from sql.conditionals import Case, Coalesce
from sql.functions import Ceil, CurrentTimestamp, DateTrunc, Log, Power, Round

try:
    import pygal
except ImportError:
    pygal = None
from dateutil.relativedelta import relativedelta

from trytond.i18n import lazy_gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction


def pairwise(iterable):
    a, b = tee(iterable)
    next(b)
    return zip_longest(a, b)


class Abstract(ModelSQL, ModelView):

    company = fields.Many2One(
        'company.company', lazy_gettext('stock.msg_stock_reporting_company'))
    cost = Monetary(
        lazy_gettext('stock.msg_stock_reporting_cost'),
        currency='currency', digits='currency')
    revenue = Monetary(
        lazy_gettext('stock.msg_stock_reporting_revenue'),
        currency='currency', digits='currency')
    profit = Monetary(
        lazy_gettext('stock.msg_stock_reporting_profit'),
        currency='currency', digits='currency')
    margin = fields.Numeric(
        lazy_gettext('stock.msg_stock_reporting_margin'),
        digits=(14, 4),
        states={
            'invisible': ~Eval('margin'),
            })
    margin_trend = fields.Function(fields.Char(
            lazy_gettext('stock.msg_stock_reporting_margin_trend')),
        'get_trend')
    time_series = None

    currency = fields.Many2One(
        'currency.currency',
        lazy_gettext('stock.msg_stock_reporting_currency'))

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
        Move = pool.get('stock.move')
        Location = pool.get('stock.location')

        tables = {}
        tables['move'] = move = Move.__table__()
        tables['move.company'] = company = Company.__table__()
        tables['move.company.currency'] = currency = Currency.__table__()
        tables['move.from_location'] = from_location = Location.__table__()
        tables['move.to_location'] = to_location = Location.__table__()
        withs = {}
        withs['currency_rate'] = currency_rate = With(
            query=Currency.currency_rate_sql())
        withs['currency_rate_company'] = currency_rate_company = With(
            query=Currency.currency_rate_sql())

        from_item = (move
            .join(currency_rate,
                condition=(move.currency == currency_rate.currency)
                & (currency_rate.start_date <= move.effective_date)
                & ((currency_rate.end_date == Null)
                    | (currency_rate.end_date >= move.effective_date))
                )
            .join(company,
                condition=move.company == company.id)
            .join(currency,
                condition=company.currency == currency.id)
            .join(currency_rate_company,
                condition=(company.currency == currency_rate_company.currency)
                & (currency_rate_company.start_date <= move.effective_date)
                & ((currency_rate_company.end_date == Null)
                    | (currency_rate_company.end_date >= move.effective_date))
                )
            .join(from_location,
                condition=(move.from_location == from_location.id))
            .join(to_location,
                condition=(move.to_location == to_location.id)))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        move = tables['move']
        from_location = tables['move.from_location']
        to_location = tables['move.to_location']
        currency = tables['move.company.currency']

        sign = Case(
            (from_location.type.in_(cls._to_location_types())
                & to_location.type.in_(cls._from_location_types()),
                -1),
            else_=1)
        cost = cls._column_cost(tables, withs, sign)
        revenue = cls._column_revenue(tables, withs, sign)
        profit = revenue - cost
        margin = Case(
            (revenue != 0, profit / revenue),
            else_=Null)
        return [
            cls._column_id(tables, withs).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            move.company.as_('company'),
            cls.cost.sql_cast(
                Round(cost, currency.digits)).as_('cost'),
            cls.revenue.sql_cast(
                Round(revenue, currency.digits)).as_('revenue'),
            cls.profit.sql_cast(
                Round(profit, currency.digits)).as_('profit'),
            cls.margin.sql_cast(
                Round(margin, cls.margin.digits[1])).as_('margin'),
            currency.id.as_('currency'),
            ]

    @classmethod
    def _column_id(cls, tables, withs):
        move = tables['move']
        return Min(move.id)

    @classmethod
    def _column_cost(cls, tables, withs, sign):
        move = tables['move']
        return Sum(
            sign * cls.cost.sql_cast(move.internal_quantity)
            * Coalesce(move.cost_price, 0))

    @classmethod
    def _column_revenue(cls, tables, withs, sign):
        move = tables['move']
        currency = withs['currency_rate']
        currency_company = withs['currency_rate_company']
        return Sum(
            sign * cls.revenue.sql_cast(move.quantity)
            * Coalesce(move.unit_price, 0)
            * Coalesce(currency_company.rate / currency.rate, 0))

    @classmethod
    def _group_by(cls, tables, withs):
        move = tables['move']
        currency = tables['move.company.currency']
        return [move.company, currency.id, currency.digits]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        move = tables['move']
        from_location = tables['move.from_location']
        to_location = tables['move.to_location']

        where = move.company == context.get('company')
        where &= ((
                from_location.type.in_(cls._from_location_types())
                & to_location.type.in_(cls._to_location_types()))
            | (
                from_location.type.in_(cls._to_location_types())
                & to_location.type.in_(cls._from_location_types())))
        where &= move.state == 'done'
        from_date = context.get('from_date')
        if from_date:
            where &= move.effective_date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= move.effective_date <= to_date
        return where

    @classmethod
    def _from_location_types(cls):
        return ['storage', 'drop']

    @classmethod
    def _to_location_types(cls):
        types = ['customer']
        if Transaction().context.get('include_lost'):
            types += ['lost_found']
        return types

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
            chart.add('', [getattr(ts, name) or 0 if ts else 0
                    for ts in self.time_series_all])
            return chart.render_sparktext()

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree/field[@name="profit"]', 'visual',
                If(Eval('profit', 0) < 0, 'danger', '')),
            ('/tree/field[@name="margin"]', 'visual',
                If(Eval('margin', 0) < 0, 'danger', '')),
            ]


class AbstractTimeseries(Abstract):

    date = fields.Date("Date")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [('date', 'ASC')]

    @classmethod
    def _columns(cls, tables, withs):
        return super()._columns(tables, withs) + [
            cls._column_date(tables, withs).as_('date')]

    @classmethod
    def _column_date(cls, tables, withs):
        context = Transaction().context
        move = tables['move']
        date = DateTrunc(context.get('period'), move.effective_date)
        date = cls.date.sql_cast(date)
        return date

    @classmethod
    def _group_by(cls, tables, withs):
        return super()._group_by(tables, withs) + [
            cls._column_date(tables, withs)]


class Context(ModelView):
    "Stock Reporting Margin Context"
    __name__ = 'stock.reporting.margin.context'

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
    include_lost = fields.Boolean(
        "Include Lost",
        help="If checked, the cost of product moved "
        "to a lost and found location is included.")

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
    def default_include_lost(cls):
        return Transaction().context.get('include_lost', False)


class Main(Abstract, ModelView):
    "Stock Reporting Margin"
    __name__ = 'stock.reporting.margin.main'

    time_series = fields.Function(fields.One2Many(
            'stock.reporting.margin.main.time_series', None, "Time Series"),
        'get_time_series')

    def get_rec_name(self, name):
        return ''

    def get_time_series(self, name):
        pool = Pool()
        Timeseries = pool.get('stock.reporting.margin.main.time_series')
        return [t.id for t in Timeseries.search([])]


class MainTimeseries(AbstractTimeseries, ModelView):
    "Stock Reporting Margin"
    __name__ = 'stock.reporting.margin.main.time_series'


class ProductMixin:
    __slots__ = ()

    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    internal_quantity = fields.Float("Internal Quantity")
    quantity = fields.Function(fields.Float(
            "Quantity", digits='unit'), 'get_quantity')
    unit = fields.Many2One('product.uom', "Unit")

    @classmethod
    def _joins(cls):
        pool = Pool()
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        from_item, tables, withs = super()._joins()
        if 'move.product' not in tables:
            product = Product.__table__()
            tables['move.product'] = product
            move = tables['move']
            from_item = (from_item
                .join(product, condition=move.product == product.id))
        if 'move.product.template' not in tables:
            template = Template.__table__()
            tables['move.product.template'] = template
            product = tables['move.product']
            from_item = (from_item
                .join(template, condition=product.template == template.id))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        move = tables['move']
        from_location = tables['move.from_location']
        to_location = tables['move.to_location']
        template = tables['move.product.template']
        sign = Case(
            (from_location.type.in_(cls._to_location_types())
                & to_location.type.in_(cls._from_location_types()),
                -1),
            else_=1)
        return super()._columns(tables, withs) + [
            move.product.as_('product'),
            Sum(sign * move.internal_quantity).as_('internal_quantity'),
            template.default_uom.as_('unit'),
            ]

    @classmethod
    def _group_by(cls, tables, withs):
        move = tables['move']
        template = tables['move.product.template']
        return super()._group_by(tables, withs) + [
            move.product, template.default_uom]

    def get_rec_name(self, name):
        return self.product.rec_name

    def get_quantity(self, name):
        return self.unit.round(self.internal_quantity)


class Product(ProductMixin, Abstract, ModelView):
    "Stock Reporting Margin per Product"
    __name__ = 'stock.reporting.margin.product'

    time_series = fields.One2Many(
        'stock.reporting.margin.product.time_series', 'product', "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        move = tables['move']
        return move.product


class ProductTimeseries(ProductMixin, AbstractTimeseries, ModelView):
    "Stock Reporting Margin per Product"
    __name__ = 'stock.reporting.margin.product.time_series'


class CategoryMixin:
    __slots__ = ()

    category = fields.Many2One('product.category', "Category")

    @classmethod
    def _joins(cls):
        pool = Pool()
        Product = pool.get('product.product')
        TemplateCategory = pool.get('product.template-product.category.all')
        from_item, tables, withs = super()._joins()
        if 'move.product' not in tables:
            product = Product.__table__()
            tables['move.product'] = product
            move = tables['move']
            from_item = (from_item
                .join(product, condition=move.product == product.id))
        if 'move.product.template_category' not in tables:
            template_category = TemplateCategory.__table__()
            tables['move.product.template_category'] = template_category
            product = tables['move.product']
            from_item = (from_item
                .join(template_category,
                    condition=product.template == template_category.template))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        template_category = tables['move.product.template_category']
        return super()._columns(tables, withs) + [
            template_category.category.as_('category')]

    @classmethod
    def _column_id(cls, tables, withs):
        pool = Pool()
        Category = pool.get('product.category')
        category = Category.__table__()
        move = tables['move']
        template_category = tables['move.product.template_category']
        # Get a stable number of category over time
        # by using number one order bigger.
        nb_category = category.select(
            Power(10, (Ceil(Log(Max(category.id))) + Literal(1))))
        return Min(move.id * nb_category + template_category.id)

    @classmethod
    def _group_by(cls, tables, withs):
        template_category = tables['move.product.template_category']
        return super()._group_by(tables, withs) + [template_category.category]

    @classmethod
    def _where(cls, tables, withs):
        template_category = tables['move.product.template_category']
        where = super()._where(tables, withs)
        where &= template_category.category != Null
        return where

    def get_rec_name(self, name):
        return self.category.rec_name if self.category else None


class Category(CategoryMixin, Abstract, ModelView):
    "Stock Reporting Margin per Category"
    __name__ = 'stock.reporting.margin.category'

    time_series = fields.One2Many(
        'stock.reporting.margin.category.time_series', 'category',
        "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('category', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        template_category = tables['move.product.template_category']
        return template_category.category


class CategoryTimeseries(CategoryMixin, AbstractTimeseries, ModelView):
    "Stock Reporting Margin per Category"
    __name__ = 'stock.reporting.margin.category.time_series'


class CategoryTree(ModelSQL, ModelView):
    "Stock Reporting Margin per Category"
    __name__ = 'stock.reporting.margin.category.tree'

    name = fields.Function(fields.Char("Name"), 'get_name')
    parent = fields.Many2One('stock.reporting.margin.category.tree', "Parent")
    children = fields.One2Many(
        'stock.reporting.margin.category.tree', 'parent', "Children")
    cost = fields.Function(Monetary(
            lazy_gettext('stock.msg_stock_reporting_cost'),
            currency='currency', digits='currency'),
        'get_total')
    revenue = fields.Function(Monetary(
            lazy_gettext('stock.msg_stock_reporting_revenue'),
            currency='currency', digits='currency'),
        'get_total')
    profit = fields.Function(Monetary(
            lazy_gettext('stock.msg_stock_reporting_profit'),
            currency='currency', digits='currency'),
        'get_total')
    margin = fields.Function(Monetary(
            lazy_gettext('stock.msg_stock_reporting_margin'),
            digits=(14, 4)),
        'get_margin')

    currency = fields.Function(fields.Many2One(
            'currency.currency',
            lazy_gettext('stock.msg_stock_reporting_currency')),
        'get_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Category = pool.get('product.category')
        return Category.__table__()

    @classmethod
    def get_name(cls, categories, name):
        pool = Pool()
        Category = pool.get('product.category')
        categories = Category.browse(categories)
        return {c.id: c.name for c in categories}

    @classmethod
    def order_name(cls, tables):
        pool = Pool()
        Category = pool.get('product.category')
        table, _ = tables[None]
        if 'category' not in tables:
            category = Category.__table__()
            tables['category'] = {
                None: (category, table.id == category.id),
                }
        return Category.name.convert_order(
            'name', tables['category'], Category)

    def time_series_all(self):
        return []

    @classmethod
    def get_total(cls, categories, names):
        pool = Pool()
        ReportingCategory = pool.get('stock.reporting.margin.category')
        table = cls.__table__()
        reporting_category = ReportingCategory.__table__()
        cursor = Transaction().connection.cursor()

        categories = cls.search([
                ('parent', 'child_of', [c.id for c in categories]),
                ])
        ids = [c.id for c in categories]
        parents = {}
        reporting_categories = []
        for sub_ids in grouped_slice(ids):
            sub_ids = list(sub_ids)
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.select(table.id, table.parent, where=where))
            parents.update(cursor)

            where = reduce_ids(reporting_category.id, sub_ids)
            cursor.execute(
                *reporting_category.select(reporting_category.id, where=where))
            reporting_categories.extend(r for r, in cursor)

        result = {}
        reporting_categories = ReportingCategory.browse(reporting_categories)
        for name in names:
            values = dict.fromkeys(ids, 0)
            values.update(
                (c.id, getattr(c, name)) for c in reporting_categories)
            result[name] = cls._sum_tree(categories, values, parents)
        return result

    @classmethod
    def _sum_tree(cls, categories, values, parents):
        result = values.copy()
        categories = set((c.id for c in categories))
        leafs = categories - set(parents.values())
        while leafs:
            for category in leafs:
                categories.remove(category)
                parent = parents.get(category)
                if parent in result:
                    result[parent] += result[category]
            next_leafs = set(categories)
            for category in categories:
                parent = parents.get(category)
                if not parent:
                    continue
                if parent in next_leafs and parent in categories:
                    next_leafs.remove(parent)
            leafs = next_leafs
        return result

    def get_margin(self, name):
        digits = self.__class__.margin.digits
        if self.profit is not None and self.revenue:
            return (self.profit / self.revenue).quantize(
                Decimal(1) / 10 ** digits[1])

    def get_currency(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.id

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('/tree/field[@name="profit"]', 'visual',
                If(Eval('profit', 0) < 0, 'danger', '')),
            ('/tree/field[@name="margin"]', 'visual',
                If(Eval('margin', 0) < 0, 'danger', '')),
            ]
