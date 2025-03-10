# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sql import Column, Literal, Null, Union, With
from sql.aggregate import Count, Max, Min, Sum
from sql.conditionals import Coalesce
from sql.functions import Ceil, CurrentTimestamp, DateTrunc, Log, Power, Round
from sql.operators import Concat

from trytond.i18n import lazy_gettext
from trytond.model import ModelSQL, ModelView, UnionMixin, fields, sum_tree
from trytond.modules.currency.fields import Monetary
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.tools import grouped_slice, pairwise_longest, reduce_ids
from trytond.tools.chart import sparkline
from trytond.transaction import Transaction
from trytond.wizard import StateAction, StateTransition, Wizard


class Abstract(ModelSQL):

    company = fields.Many2One(
        'company.company', lazy_gettext("sale.msg_sale_reporting_company"))
    number = fields.Integer(lazy_gettext("sale.msg_sale_reporting_number"),
        help=lazy_gettext("sale.msg_sale_reporting_number_help"))
    revenue = Monetary(
        lazy_gettext("sale.msg_sale_reporting_revenue"),
        digits='currency', currency='currency')
    revenue_trend = fields.Function(
        fields.Char(lazy_gettext("sale.msg_sale_reporting_revenue_trend")),
        'get_trend')
    time_series = None

    currency = fields.Many2One(
        'currency.currency', lazy_gettext("sale.msg_sale_reporting_currency"))

    @classmethod
    def table_query(cls):
        from_item, tables, withs = cls._joins()
        return from_item.select(*cls._columns(tables, withs),
            where=cls._where(tables, withs),
            group_by=cls._group_by(tables, withs),
            with_=withs.values())

    @classmethod
    def _sale_line(cls, length, index, company_id=None):
        pool = Pool()
        Line = pool.get('sale.line')
        Sale = pool.get('sale.sale')

        line = Line.__table__()
        sale = Sale.__table__()

        return (line
            .join(sale, condition=line.sale == sale.id)
            .select(
                (line.id * length + index).as_('id'),
                *cls._sale_line_columns(line, sale),
                where=sale.state.in_(cls._sale_states())
                & (sale.company == company_id),
                ))

    @classmethod
    def _sale_line_columns(cls, line, sale):
        return [
            line.product.as_('product'),
            Coalesce(line.actual_quantity, line.quantity).as_('quantity'),
            line.unit_price.as_('unit_price'),
            Concat('sale.sale,', line.sale).as_('order'),
            sale.sale_date.as_('date'),
            sale.company.as_('company'),
            sale.currency.as_('currency'),
            sale.party.as_('customer'),
            sale.warehouse.as_('location'),
            sale.shipment_address.as_('shipment_address'),
            ]

    @classmethod
    def _lines(cls):
        return [cls._sale_line]

    @classmethod
    def _joins(cls):
        pool = Pool()
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        context = Transaction().context

        tables = {}
        company = context.get('company')
        lines = cls._lines()
        tables['line'] = line = Union(*(
                l(len(lines), i, company) for i, l in enumerate(lines)))
        tables['line.company'] = company = Company.__table__()
        tables['line.company.currency'] = currency = Currency.__table__()
        withs = {}
        currency_sale = With(query=Currency.currency_rate_sql())
        withs['currency_sale'] = currency_sale
        currency_company = With(query=Currency.currency_rate_sql())
        withs['currency_company'] = currency_company

        from_item = (line
            .join(currency_sale,
                condition=(line.currency == currency_sale.currency)
                & (currency_sale.start_date <= line.date)
                & ((currency_sale.end_date == Null)
                    | (currency_sale.end_date > line.date))
                )
            .join(company, condition=line.company == company.id)
            .join(currency, condition=company.currency == currency.id)
            .join(currency_company,
                condition=(company.currency == currency_company.currency)
                & (currency_company.start_date <= line.date)
                & ((currency_company.end_date == Null)
                    | (currency_company.end_date > line.date))
                ))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        line = tables['line']
        currency = tables['line.company.currency']
        currency_company = withs['currency_company']
        currency_sale = withs['currency_sale']

        revenue = Round(cls.revenue.sql_cast(
                Sum(line.quantity * line.unit_price
                    * currency_company.rate / currency_sale.rate)),
            currency.digits)
        return [
            cls._column_id(tables, withs).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            line.company.as_('company'),
            revenue.as_('revenue'),
            Count(line.order, distinct=True).as_('number'),
            currency.id.as_('currency'),
            ]

    @classmethod
    def _column_id(cls, tables, withs):
        line = tables['line']
        return Min(line.id)

    @classmethod
    def _group_by(cls, tables, withs):
        line = tables['line']
        currency = tables['line.company.currency']
        return [line.company, currency.id, currency.digits]

    @classmethod
    def _where(cls, tables, withs):
        pool = Pool()
        Location = pool.get('stock.location')
        context = Transaction().context
        line = tables['line']

        where = Literal(True)
        from_date = context.get('from_date')
        if from_date:
            where &= line.date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= line.date <= to_date
        warehouse = context.get('warehouse')
        if warehouse:
            locations = Location.search([
                    ('parent', 'child_of', warehouse),
                    ],
                query=True)
            where &= line.location.in_(locations)
        return where

    @classmethod
    def _sale_states(cls):
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
        return sparkline([
                getattr(ts, name) if ts else 0 for ts in self.time_series_all])


class AbstractTimeseries(Abstract):

    date = fields.Date(lazy_gettext('sale.msg_sale_reporting_date'))

    @classmethod
    def __setup__(cls):
        super(AbstractTimeseries, cls).__setup__()
        cls._order = [('date', 'ASC')]

    @classmethod
    def _columns(cls, tables, withs):
        return super(AbstractTimeseries, cls)._columns(tables, withs) + [
            cls._column_date(tables, withs).as_('date')]

    @classmethod
    def _column_date(cls, tables, withs):
        context = Transaction().context
        line = tables['line']
        date = DateTrunc(context.get('period'), line.date)
        date = cls.date.sql_cast(date)
        return date

    @classmethod
    def _group_by(cls, tables, withs):
        return super(AbstractTimeseries, cls)._group_by(tables, withs) + [
            cls._column_date(tables, withs)]


class Context(ModelView):
    "Sale Reporting Context"
    __name__ = 'sale.reporting.context'

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
    "Sale Reporting"
    __name__ = 'sale.reporting.main'

    time_series = fields.Function(fields.One2Many(
            'sale.reporting.main.time_series', None,
            lazy_gettext('sale.msg_sale_reporting_time_series')),
        'get_time_series')

    def get_rec_name(self, name):
        return ''

    def get_time_series(self, name):
        pool = Pool()
        Timeseries = pool.get('sale.reporting.main.time_series')
        return [t.id for t in Timeseries.search([])]


class MainTimeseries(AbstractTimeseries, ModelView):
    "Sale Reporting"
    __name__ = 'sale.reporting.main.time_series'


class CustomerMixin(object):
    __slots__ = ()
    customer = fields.Many2One(
        'party.party', "Customer",
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})

    @classmethod
    def _columns(cls, tables, withs):
        line = tables['line']
        return super(CustomerMixin, cls)._columns(tables, withs) + [
            line.customer.as_('customer')]

    @classmethod
    def _group_by(cls, tables, withs):
        line = tables['line']
        return super(CustomerMixin, cls)._group_by(tables, withs) + [
            line.customer]

    def get_rec_name(self, name):
        return self.customer.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('customer.rec_name', *clause[1:])]


class Customer(CustomerMixin, Abstract, ModelView):
    "Sale Reporting per Customer"
    __name__ = 'sale.reporting.customer'

    time_series = fields.One2Many(
        'sale.reporting.customer.time_series', 'customer',
        lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('customer', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        line = tables['line']
        return line.customer

    @classmethod
    def _where(cls, tables, withs):
        line = tables['line']
        where = super()._where(tables, withs)
        where &= line.customer != Null
        return where


class CustomerTimeseries(CustomerMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Customer"
    __name__ = 'sale.reporting.customer.time_series'


class CustomerCategoryMixin:
    __slots__ = ()
    category = fields.Many2One('party.category', "Category")

    @classmethod
    def _joins(cls):
        pool = Pool()
        PartyCategory = pool.get('party.party-party.category')
        from_item, tables, withs = super()._joins()
        if 'line.customer.party_category' not in tables:
            party_category = PartyCategory.__table__()
            tables['line.customer.party_category'] = party_category
            line = tables['line']
            from_item = (from_item
                .join(party_category,
                    condition=line.customer == party_category.party))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        party_category = tables['line.customer.party_category']
        return super()._columns(tables, withs) + [
            party_category.category.as_('category')]

    @classmethod
    def _column_id(cls, tables, withs):
        pool = Pool()
        Category = pool.get('party.category')
        category = Category.__table__()
        line = tables['line']
        party_category = tables['line.customer.party_category']
        # Get a stable number of categories over time
        # by using a number one order bigger.
        nb_category = category.select(
            Power(10, (Ceil(Log(Max(category.id))) + Literal(1))))
        return Min(line.id * nb_category + party_category.id)

    @classmethod
    def _group_by(cls, tables, withs):
        party_category = tables['line.customer.party_category']
        return super()._group_by(tables, withs) + [party_category.category]

    @classmethod
    def _where(cls, tables, withs):
        party_category = tables['line.customer.party_category']
        where = super()._where(tables, withs)
        where &= party_category.category != Null
        return where

    def get_rec_name(self, name):
        return self.category.rec_name if self.category else None

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('category.rec_name', *clause[1:])]


class CustomerCategory(CustomerCategoryMixin, Abstract, ModelView):
    "Sale Reporting per Customer Category"
    __name__ = 'sale.reporting.customer.category'

    time_series = fields.One2Many(
        'sale.reporting.customer.category.time_series', 'category',
        lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('category', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        party_category = tables['line.customer.party_category']
        return party_category.category


class CustomerCategoryTimeseries(
        CustomerCategoryMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Customer Category"
    __name__ = 'sale.reporting.customer.category.time_series'


class CustomerCategoryTree(ModelSQL, ModelView):
    "Sale Reporting per Customer Category"
    __name__ = 'sale.reporting.customer.category.tree'

    name = fields.Function(
        fields.Char("Name"), 'get_name', searcher='search_name')
    parent = fields.Many2One('sale.reporting.customer.category.tree', "Parent")
    children = fields.One2Many(
        'sale.reporting.customer.category.tree', 'parent', "Children")
    revenue = fields.Function(Monetary(
            "Revenue", digits='currency', currency='currency'), 'get_total')

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Category = pool.get('party.category')
        return Category.__table__()

    @classmethod
    def get_name(cls, categories, name):
        pool = Pool()
        Category = pool.get('party.category')
        categories = Category.browse(categories)
        return {c.id: c.name for c in categories}

    @classmethod
    def search_name(cls, name, clause):
        pool = Pool()
        Category = pool.get('party.category')
        return [('id', 'in', Category.search([clause], query=True))]

    @classmethod
    def order_name(cls, tables):
        pool = Pool()
        Category = pool.get('party.category')
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
        ReportingCustomerCategory = pool.get(
            'sale.reporting.customer.category')
        reporting_product_category = ReportingCustomerCategory.__table__()
        cursor = Transaction().connection.cursor()

        categories = cls.search([
                ('parent', 'child_of', [c.id for c in categories]),
                ])
        ids = [c.id for c in categories]
        reporting_customer_categories = []
        for sub_ids in grouped_slice(ids):
            sub_ids = list(sub_ids)
            where = reduce_ids(reporting_product_category.id, sub_ids)
            cursor.execute(
                *reporting_product_category.select(
                    reporting_product_category.id, where=where))
            reporting_customer_categories.extend(r for r, in cursor)

        result = {}
        reporting_product_categories = ReportingCustomerCategory.browse(
            reporting_customer_categories)
        for name in names:
            values = defaultdict(Decimal,
                {c.id: getattr(c, name) for c in reporting_product_categories})
            result[name] = sum_tree(categories, values)
        return result

    def get_currency(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company is not None and company >= 0:
            return Company(company).currency.id


class ProductMixin(object):
    __slots__ = ()
    product = fields.Many2One(
        'product.product', "Product",
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})

    @classmethod
    def _columns(cls, tables, withs):
        line = tables['line']
        return super(ProductMixin, cls)._columns(tables, withs) + [
            line.product.as_('product')]

    @classmethod
    def _group_by(cls, tables, withs):
        line = tables['line']
        return super(ProductMixin, cls)._group_by(tables, withs) + [
            line.product]

    @classmethod
    def _where(cls, tables, withs):
        line = tables['line']
        where = super(ProductMixin, cls)._where(tables, withs)
        where &= line.product != Null
        return where

    def get_rec_name(self, name):
        return self.product.rec_name if self.product else None

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('product.rec_name', *clause[1:])]


class Product(ProductMixin, Abstract, ModelView):
    "Sale Reporting per Product"
    __name__ = 'sale.reporting.product'

    time_series = fields.One2Many(
        'sale.reporting.product.time_series', 'product',
        lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('product', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        line = tables['line']
        return line.product


class ProductTimeseries(ProductMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Product"
    __name__ = 'sale.reporting.product.time_series'


class ProductCategoryMixin(object):
    __slots__ = ()
    category = fields.Many2One(
        'product.category', "Category",
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})

    @classmethod
    def _joins(cls):
        pool = Pool()
        Product = pool.get('product.product')
        TemplateCategory = pool.get('product.template-product.category.all')
        from_item, tables, withs = super()._joins()
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
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        template_category = tables['line.product.template_category']
        return super()._columns(tables, withs) + [
            template_category.category.as_('category')]

    @classmethod
    def _column_id(cls, tables, withs):
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
    def _group_by(cls, tables, withs):
        template_category = tables['line.product.template_category']
        return super()._group_by(tables, withs) + [template_category.category]

    @classmethod
    def _where(cls, tables, withs):
        template_category = tables['line.product.template_category']
        where = super()._where(tables, withs)
        where &= template_category.category != Null
        return where

    def get_rec_name(self, name):
        return self.category.rec_name if self.category else None

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('category.rec_name', *clause[1:])]


class ProductCategory(ProductCategoryMixin, Abstract, ModelView):
    "Sale Reporting per Product Category"
    __name__ = 'sale.reporting.product.category'

    time_series = fields.One2Many(
        'sale.reporting.product.category.time_series', 'category',
        lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('category', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        template_category = tables['line.product.template_category']
        return template_category.category


class ProductCategoryTimeseries(
        ProductCategoryMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Product Category"
    __name__ = 'sale.reporting.product.category.time_series'


class ProductCategoryTree(ModelSQL, ModelView):
    "Sale Reporting per Product Category"
    __name__ = 'sale.reporting.product.category.tree'

    name = fields.Function(
        fields.Char("Name"), 'get_name', searcher='search_name')
    parent = fields.Many2One('sale.reporting.product.category.tree', "Parent")
    children = fields.One2Many(
        'sale.reporting.product.category.tree', 'parent', "Children")
    revenue = fields.Function(Monetary(
            "Revenue", digits='currency'), 'get_total')

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_currency')

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
    def search_name(cls, name, clause):
        pool = Pool()
        Category = pool.get('product.category')
        return [('id', 'in', Category.search([clause], query=True))]

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
        ReportingProductCategory = pool.get('sale.reporting.product.category')
        reporting_product_category = ReportingProductCategory.__table__()
        cursor = Transaction().connection.cursor()

        categories = cls.search([
                ('parent', 'child_of', [c.id for c in categories]),
                ])
        ids = [c.id for c in categories]
        reporting_product_categories = []
        for sub_ids in grouped_slice(ids):
            sub_ids = list(sub_ids)
            where = reduce_ids(reporting_product_category.id, sub_ids)
            cursor.execute(
                *reporting_product_category.select(
                    reporting_product_category.id, where=where))
            reporting_product_categories.extend(r for r, in cursor)

        result = {}
        reporting_product_categories = ReportingProductCategory.browse(
            reporting_product_categories)
        for name in names:
            values = defaultdict(
                Decimal,
                {c.id: getattr(c, name) for c in reporting_product_categories})
            result[name] = sum_tree(categories, values)
        return result

    def get_currency(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company is not None and company >= 0:
            return Company(company).currency.id


class CountryMixin(object):
    __slots__ = ()
    country = fields.Many2One('country.country', "Country")

    @classmethod
    def _joins(cls):
        pool = Pool()
        Address = pool.get('party.address')
        from_item, tables, withs = super(CountryMixin, cls)._joins()
        if 'line.shipment_address' not in tables:
            address = Address.__table__()
            tables['line.shipment_address'] = address
            line = tables['line']
            from_item = (from_item
                .join(address, condition=line.shipment_address == address.id))
        return from_item, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        address = tables['line.shipment_address']
        return super(CountryMixin, cls)._columns(tables, withs) + [
            address.country.as_('country')]

    @classmethod
    def _group_by(cls, tables, withs):
        address = tables['line.shipment_address']
        return super(CountryMixin, cls)._group_by(tables, withs) + [
            address.country]

    @classmethod
    def _where(cls, tables, withs):
        address = tables['line.shipment_address']
        where = super(CountryMixin, cls)._where(tables, withs)
        where &= address.country != Null
        return where

    def get_rec_name(self, name):
        return self.country.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('country.rec_name', *clause[1:])]


class RegionTree(ModelSQL, ModelView):
    "Sale Reporting per Region"
    __name__ = 'sale.reporting.region.tree'

    name = fields.Function(
        fields.Char("Name"), 'get_name', searcher='search_name')
    parent = fields.Many2One('sale.reporting.region.tree', "Parent")
    subregions = fields.One2Many(
        'sale.reporting.region.tree', 'parent', "Subregions")

    revenue = fields.Function(Monetary(
            "Revenue", digits='currency'), 'get_total')

    currency = fields.Function(fields.Many2One(
            'currency.currency', "Currency"), 'get_currency')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Region = pool.get('country.region')
        return Region.__table__()

    @classmethod
    def get_name(cls, regions, name):
        pool = Pool()
        Region = pool.get('country.region')
        regions = Region.browse(regions)
        return {r.id: r.name for r in regions}

    @classmethod
    def search_name(cls, name, domain):
        pool = Pool()
        Region = pool.get('country.region')
        return [('id', 'in', Region.search(domain, query=True))]

    @classmethod
    def order_name(cls, tables):
        pool = Pool()
        Region = pool.get('country.region')
        table, _ = tables[None]
        if 'region' not in tables:
            region = Region.__table__()
            tables['region'] = {
                None: (region, table.id == region.id),
                }
        return Region.name.convert_order(
                'name', tables['region'], Region)

    @classmethod
    def get_total(cls, regions, names):
        pool = Pool()
        ReportingCountry = pool.get('sale.reporting.country')

        regions = cls.search([
                ('parent', 'child_of', [r.id for r in regions]),
                ])
        reporting_countries = []

        result = {}
        reporting_countries = ReportingCountry.search([
                ('country.region', 'in', [r.id for r in regions]),
                ])
        for name in names:
            values = defaultdict(Decimal)
            for reporting_country in reporting_countries:
                values[reporting_country.country.region.id] += (
                    getattr(reporting_country, name))
            result[name] = sum_tree(regions, values)
        return result

    def get_currency(self, name):
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company is not None and company >= 0:
            return Company(company).currency.id


class OpenRegionTree(Wizard):
    "Open Region"
    __name__ = 'sale.reporting.region.tree.open'

    start = StateAction('sale.act_reporting_country_tree')

    def do_start(self, action):
        pool = Pool()
        Country = pool.get('country.country')
        CountryTree = pool.get('sale.reporting.country.tree')
        countries = Country.search([
                ('region', 'child_of', [r.id for r in self.records], 'parent'),
                ])
        ids = [
            CountryTree.union_shard(c.id, 'sale.reporting.country')
            for c in countries]
        data = {
            'ids': ids,
            }
        name_suffix = ', '.join(r.rec_name for r in self.records[:5])
        if len(self.records) > 5:
            name_suffix += ',...'
        action['name'] += ' (%s)' % name_suffix
        return action, data


class Country(CountryMixin, Abstract):
    "Sale Reporting per Country"
    __name__ = 'sale.reporting.country'

    time_series = fields.One2Many(
        'sale.reporting.country.time_series', 'country',
        lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('country', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        address = tables['line.shipment_address']
        return address.country


class CountryTimeseries(CountryMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Country"
    __name__ = 'sale.reporting.country.time_series'


class SubdivisionMixin(CountryMixin):
    __slots__ = ()
    subdivision = fields.Many2One('country.subdivision', "Subdivision")

    @classmethod
    def _columns(cls, tables, withs):
        address = tables['line.shipment_address']
        return super(SubdivisionMixin, cls)._columns(tables, withs) + [
            address.subdivision.as_('subdivision')]

    @classmethod
    def _group_by(cls, tables, withs):
        address = tables['line.shipment_address']
        return super(SubdivisionMixin, cls)._group_by(tables, withs) + [
            address.subdivision]

    @classmethod
    def _where(cls, tables, withs):
        address = tables['line.shipment_address']
        where = super(SubdivisionMixin, cls)._where(tables, withs)
        where &= address.subdivision != Null
        return where

    def get_rec_name(self, name):
        return self.subdivision.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('subdivision.rec_name', *clause[1:])]


class Subdivision(SubdivisionMixin, Abstract):
    "Sale Reporting per Subdivision"
    __name__ = 'sale.reporting.country.subdivision'

    time_series = fields.One2Many(
        'sale.reporting.country.subdivision.time_series', 'subdivision',
        lazy_gettext('sale.msg_sale_reporting_time_series'))

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('subdivision', 'ASC'))

    @classmethod
    def _column_id(cls, tables, withs):
        address = tables['line.shipment_address']
        return address.subdivision


class SubdivisionTimeseries(SubdivisionMixin, AbstractTimeseries, ModelView):
    "Sale Reporting per Subdivision"
    __name__ = 'sale.reporting.country.subdivision.time_series'


class CountryTree(UnionMixin, Abstract, ModelView):
    "Sale Reporting per Country"
    __name__ = 'sale.reporting.country.tree'

    region = fields.Function(fields.Char("Region"), 'get_rec_name')
    parent = fields.Many2One('sale.reporting.country.tree', "Parent")
    children = fields.One2Many(
        'sale.reporting.country.tree', 'parent', "Children")

    @classmethod
    def union_models(cls):
        return ['sale.reporting.country', 'sale.reporting.country.subdivision']

    @classmethod
    def union_column(cls, name, field, table, Model):
        column = super().union_column(
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


class OpenCountryTree(Wizard):
    "Open Country"
    __name__ = 'sale.reporting.country.tree.open'

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
