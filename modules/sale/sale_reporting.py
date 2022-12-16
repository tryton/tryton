# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from itertools import tee, zip_longest

try:
    import pygal
except ImportError:
    pygal = None
from dateutil.relativedelta import relativedelta
from sql import Null, Literal, Column
from sql.aggregate import Sum, Max, Min, Count
from sql.conditionals import Coalesce
from sql.functions import CurrentTimestamp, DateTrunc, Power, Ceil, Log

from trytond.pool import Pool
from trytond.model import ModelSQL, ModelView, UnionMixin, fields
from trytond.tools import grouped_slice, reduce_ids
from trytond.transaction import Transaction
from trytond.pyson import Eval, If
from trytond.wizard import Wizard, StateTransition, StateAction
from trytond.i18n import lazy_gettext


def pairwise(iterable):
    a, b = tee(iterable)
    next(b)
    return zip_longest(a, b)


class Abstract(ModelSQL):

    company = fields.Many2One(
        'company.company', lazy_gettext("sale.msg_sale_reporting_company"))
    number = fields.Integer(lazy_gettext("sale.msg_sale_reporting_number"),
        help=lazy_gettext("sale.msg_sale_reporting_number_help"))
    revenue = fields.Numeric(
        lazy_gettext("sale.msg_sale_reporting_revenue"),
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    revenue_trend = fields.Function(
        fields.Char(lazy_gettext("sale.msg_sale_reporting_revenue_trend")),
        'get_trend')
    time_series = None

    currency = fields.Function(fields.Many2One(
            'currency.currency',
            lazy_gettext("sale.msg_sale_reporting_currency")),
        'get_currency')
    currency_digits = fields.Function(
        fields.Integer(
            lazy_gettext("sale.msg_sale_reporting_currency_digits")),
        'get_currency_digits')

    @classmethod
    def table_query(cls):
        from_item, tables = cls._joins()
        return from_item.select(*cls._columns(tables),
            where=cls._where(tables),
            group_by=cls._group_by(tables))

    @classmethod
    def _joins(cls):
        pool = Pool()
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Line = pool.get('sale.line')
        Sale = pool.get('sale.sale')

        tables = {}
        tables['line'] = line = Line.__table__()
        tables['line.sale'] = sale = Sale.__table__()
        tables['line.sale.company'] = company = Company.__table__()
        currency_sale = Currency.currency_rate_sql()
        tables['currency_sale'] = currency_sale
        currency_company = Currency.currency_rate_sql()
        tables['currency_company'] = currency_company

        from_item = (line
            .join(sale, condition=line.sale == sale.id)
            .join(currency_sale,
                condition=(sale.currency == currency_sale.currency)
                & (currency_sale.start_date <= sale.sale_date)
                & ((currency_sale.end_date == Null)
                    | (currency_sale.end_date >= sale.sale_date))
                )
            .join(company, condition=sale.company == company.id)
            .join(currency_company,
                condition=(company.currency == currency_company.currency)
                & (currency_company.start_date <= sale.sale_date)
                & ((currency_company.end_date == Null)
                    | (currency_company.end_date >= sale.sale_date))
                ))
        return from_item, tables

    @classmethod
    def _columns(cls, tables):
        line = tables['line']
        sale = tables['line.sale']
        currency_company = tables['currency_company']
        currency_sale = tables['currency_sale']

        quantity = Coalesce(line.actual_quantity, line.quantity)
        revenue = cls.revenue.sql_cast(
            Sum(quantity * line.unit_price
                * currency_company.rate / currency_sale.rate))
        return [
            cls._column_id(tables).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            sale.company.as_('company'),
            revenue.as_('revenue'),
            Count(sale.id, distinct=True).as_('number'),
            ]

    @classmethod
    def _column_id(cls, tables):
        line = tables['line']
        return Min(line.id)

    @classmethod
    def _group_by(cls, tables):
        sale = tables['line.sale']
        return [sale.company]

    @classmethod
    def _where(cls, tables):
        context = Transaction().context
        sale = tables['line.sale']

        where = sale.company == context.get('company')
        where &= sale.state.in_(cls._sale_states())
        from_date = context.get('from_date')
        if from_date:
            where &= sale.sale_date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= sale.sale_date <= to_date
        warehouse = context.get('warehouse')
        if warehouse:
            where &= sale.warehouse == warehouse
        return where

    @classmethod
    def _sale_states(cls):
        return ['confirmed', 'processing', 'done']

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
            chart.add('', [getattr(ts, name) if ts else 0
                    for ts in self.time_series_all])
            return chart.render_sparktext()

    def get_currency(self, name):
        return self.company.currency.id

    def get_currency_digits(self, name):
        return self.company.currency.digits


class AbstractTimeseries(Abstract):

    date = fields.Date("Date")

    @classmethod
    def __setup__(cls):
        super(AbstractTimeseries, cls).__setup__()
        cls._order = [('date', 'ASC')]

    @classmethod
    def _columns(cls, tables):
        return super(AbstractTimeseries, cls)._columns(tables) + [
            cls._column_date(tables).as_('date')]

    @classmethod
    def _column_date(cls, tables):
        context = Transaction().context
        sale = tables['line.sale']
        date = DateTrunc(context.get('period'), sale.sale_date)
        date = cls.date.sql_cast(date)
        return date

    @classmethod
    def _group_by(cls, tables):
        return super(AbstractTimeseries, cls)._group_by(tables) + [
            cls._column_date(tables)]


class Context(ModelView):
    "Sale Reporting Context"
    __name__ = 'sale.reporting.context'

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


class CustomerMixin(object):
    __slots__ = ()
    customer = fields.Many2One('party.party', "Customer")

    @classmethod
    def _columns(cls, tables):
        sale = tables['line.sale']
        return super(CustomerMixin, cls)._columns(tables) + [
            sale.party.as_('customer')]

    @classmethod
    def _group_by(cls, tables):
        sale = tables['line.sale']
        return super(CustomerMixin, cls)._group_by(tables) + [sale.party]

    def get_rec_name(self, name):
        return self.customer.rec_name


class Customer(CustomerMixin, Abstract, ModelView):
    "Sale Reporting per Customer"
    __name__ = 'sale.reporting.customer'

    time_series = fields.One2Many(
        'sale.reporting.customer.time_series', 'customer', "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('customer', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        sale = tables['line.sale']
        return sale.party


class CustomerTimeseries(CustomerMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Customer"
    __name__ = 'sale.reporting.customer.time_series'


class ProductMixin(object):
    __slots__ = ()
    product = fields.Many2One('product.product', "Product")

    @classmethod
    def _columns(cls, tables):
        line = tables['line']
        return super(ProductMixin, cls)._columns(tables) + [
            line.product.as_('product')]

    @classmethod
    def _group_by(cls, tables):
        line = tables['line']
        return super(ProductMixin, cls)._group_by(tables) + [line.product]

    @classmethod
    def _where(cls, tables):
        line = tables['line']
        where = super(ProductMixin, cls)._where(tables)
        where &= line.product != Null
        return where

    def get_rec_name(self, name):
        return self.product.rec_name if self.product else None


class Product(ProductMixin, Abstract, ModelView):
    "Sale Reporting per Product"
    __name__ = 'sale.reporting.product'

    time_series = fields.One2Many(
        'sale.reporting.product.time_series', 'product', "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        line = tables['line']
        return line.product


class ProductTimeseries(ProductMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Product"
    __name__ = 'sale.reporting.product.time_series'


class CategoryMixin(object):
    __slots__ = ()
    category = fields.Many2One('product.category', "Category")

    @classmethod
    def _joins(cls):
        pool = Pool()
        Product = pool.get('product.product')
        TemplateCategory = pool.get('product.template-product.category.all')
        from_item, tables = super(CategoryMixin, cls)._joins()
        if 'line.product' not in tables:
            product = Product.__table__()
            tables['line.product'] = product
            line = tables['line']
            from_item = (from_item
                .join(product, condition=line.product == product.id))
        if 'line.product.template_category' not in tables:
            template_category = TemplateCategory.__table__()
            tables['line.product.template_category'] = template_category
            product = tables['line.product']
            from_item = (from_item
                .join(template_category,
                    condition=product.template == template_category.template))
        return from_item, tables

    @classmethod
    def _columns(cls, tables):
        template_category = tables['line.product.template_category']
        return super(CategoryMixin, cls)._columns(tables) + [
            template_category.category.as_('category')]

    @classmethod
    def _column_id(cls, tables):
        pool = Pool()
        Category = pool.get('product.category')
        category = Category.__table__()
        line = tables['line']
        template_category = tables['line.product.template_category']
        # Get a stable number of category over time
        # by using number one order bigger.
        nb_category = category.select(
            Power(10, (Ceil(Log(Max(category.id))) + Literal(1))))
        return Min(line.id * nb_category + template_category.id)

    @classmethod
    def _group_by(cls, tables):
        template_category = tables['line.product.template_category']
        return super(CategoryMixin, cls)._group_by(tables) + [
            template_category.category]

    @classmethod
    def _where(cls, tables):
        template_category = tables['line.product.template_category']
        where = super(CategoryMixin, cls)._where(tables)
        where &= template_category.category != Null
        return where

    def get_rec_name(self, name):
        return self.category.rec_name if self.category else None


class Category(CategoryMixin, Abstract, ModelView):
    "Sale Reporting per Category"
    __name__ = 'sale.reporting.category'

    time_series = fields.One2Many(
        'sale.reporting.category.time_series', 'category', "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('category', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        template_category = tables['line.product.template_category']
        return template_category.category


class CategoryTimeseries(CategoryMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Category"
    __name__ = 'sale.reporting.category.time_series'


class CategoryTree(ModelSQL, ModelView):
    "Sale Reporting per Category"
    __name__ = 'sale.reporting.category.tree'

    name = fields.Function(fields.Char("Name"), 'get_name')
    parent = fields.Many2One('sale.reporting.category.tree', "Parent")
    children = fields.One2Many(
        'sale.reporting.category.tree', 'parent', "Children")
    revenue = fields.Function(
        fields.Numeric("Revenue", digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']), 'get_total')

    currency_digits = fields.Function(
        fields.Integer("Currency Digits"), 'get_currency_digits')

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
        ReportingCategory = pool.get('sale.reporting.category')
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
            parents.update(cursor.fetchall())

            where = reduce_ids(reporting_category.id, sub_ids)
            cursor.execute(
                *reporting_category.select(reporting_category.id, where=where))
            reporting_categories.extend(r for r, in cursor.fetchall())

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

    def get_currency_digits(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            return Company(company).currency.digits


class CountryMixin(object):
    __slots__ = ()
    country = fields.Many2One('country.country', "Country")

    @classmethod
    def _joins(cls):
        pool = Pool()
        Address = pool.get('party.address')
        from_item, tables = super(CountryMixin, cls)._joins()
        if 'line.sale.shipment_address' not in tables:
            address = Address.__table__()
            tables['line.sale.shipment_address'] = address
            sale = tables['line.sale']
            from_item = (from_item
                .join(address, condition=sale.shipment_address == address.id))
        return from_item, tables

    @classmethod
    def _columns(cls, tables):
        address = tables['line.sale.shipment_address']
        return super(CountryMixin, cls)._columns(tables) + [
            address.country.as_('country')]

    @classmethod
    def _group_by(cls, tables):
        address = tables['line.sale.shipment_address']
        return super(CountryMixin, cls)._group_by(tables) + [address.country]

    @classmethod
    def _where(cls, tables):
        address = tables['line.sale.shipment_address']
        where = super(CountryMixin, cls)._where(tables)
        where &= address.country != Null
        return where


class Country(CountryMixin, Abstract):
    "Sale Reporting per Country"
    __name__ = 'sale.reporting.country'

    time_series = fields.One2Many(
        'sale.reporting.country.time_series', 'country', "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('country', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        address = tables['line.sale.shipment_address']
        return address.country

    def get_rec_name(self, name):
        return self.country.rec_name


class CountryTimeseries(CountryMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Country"
    __name__ = 'sale.reporting.country.time_series'


class SubdivisionMixin(CountryMixin):
    __slots__ = ()
    subdivision = fields.Many2One('country.subdivision', "Subdivision")

    @classmethod
    def _columns(cls, tables):
        address = tables['line.sale.shipment_address']
        return super(SubdivisionMixin, cls)._columns(tables) + [
            address.subdivision.as_('subdivision')]

    @classmethod
    def _group_by(cls, tables):
        address = tables['line.sale.shipment_address']
        return super(SubdivisionMixin, cls)._group_by(tables) + [
            address.subdivision]

    @classmethod
    def _where(cls, tables):
        address = tables['line.sale.shipment_address']
        where = super(SubdivisionMixin, cls)._where(tables)
        where &= address.subdivision != Null
        return where


class Subdivision(SubdivisionMixin, Abstract):
    "Sale Reporting per Subdivision"
    __name__ = 'sale.reporting.country.subdivision'

    time_series = fields.One2Many(
        'sale.reporting.country.subdivision.time_series', 'subdivision',
        "Time Series")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('subdivision', 'ASC'))

    @classmethod
    def _column_id(cls, tables):
        address = tables['line.sale.shipment_address']
        return address.subdivision

    def get_rec_name(self, name):
        return self.subdivision.rec_name


class SubdivisionTimeseries(SubdivisionMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Subdivision"
    __name__ = 'sale.reporting.country.subdivision.time_series'


class Region(UnionMixin, Abstract, ModelView):
    "Sale Reporting per Region"
    __name__ = 'sale.reporting.region'

    region = fields.Function(fields.Char("Region"), 'get_rec_name')
    parent = fields.Many2One('sale.reporting.region', "Parent")
    children = fields.One2Many('sale.reporting.region', 'parent', "Children")

    @classmethod
    def union_models(cls):
        return ['sale.reporting.country', 'sale.reporting.country.subdivision']

    @classmethod
    def union_column(cls, name, field, table, Model):
        column = super(Region, cls).union_column(
            name, field, table, Model)
        if (name == 'parent'
                and Model.__name__ == 'sale.reporting.country.subdivision'):
            column = cls.union_shard(
                Column(table, 'country'), 'sale.reporting.country')
        return column

    @classmethod
    def get_rec_name(cls, records, name):
        names = {}
        classes = defaultdict(list)
        for record in records:
            record = cls.union_unshard(record.id)
            classes[record.__class__].append(record)
        for klass, records in classes.items():
            for record in klass.browse(records):
                names[cls.union_shard(record.id, klass.__name__)] = (
                    record.rec_name)
        return names

    @property
    def time_series(self):
        record = self.union_unshard(self.id)
        return record.time_series


class OpenRegion(Wizard):
    "Open Region"
    __name__ = 'sale.reporting.region.open'

    start = StateTransition()
    country = StateAction('sale.act_reporting_country_time_series')
    subdivision = StateAction(
        'sale.act_reporting_country_subdivision_time_series')

    def transition_start(self):
        pool = Pool()
        Country = pool.get('sale.reporting.country')
        Subdivision = pool.get('sale.reporting.country.subdivision')
        record = self.model.union_unshard(self.record.id)
        if isinstance(record, Country):
            return 'country'
        elif isinstance(record, Subdivision):
            return 'subdivision'

    def _do_action(self, action):
        record = self.model.union_unshard(self.record.id)
        data = {
            'id': record.id,
            'ids': [record.id],
            }
        action['name'] += ' (%s)' % record.rec_name
        return action, data
    do_country = _do_action
    do_subdivision = _do_action
