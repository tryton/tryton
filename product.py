# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits


class Configuration(metaclass=PoolMeta):
    __name__ = 'product.configuration'

    default_lead_time = fields.MultiValue(
        fields.TimeDelta(
            "Default Lead Time",
            help="The time from confirming the sales order to sending the "
            "products.\n"
            "Used for products without a lead time."))

    @classmethod
    def default_default_lead_time(cls, **pattern):
        return datetime.timedelta(0)


class DefaultLeadTime(ModelSQL, CompanyValueMixin):
    "Product Default Lead Time"
    __name__ = 'product.configuration.default_lead_time'
    default_lead_time = fields.TimeDelta("Default Lead Time")


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    salable = fields.Boolean("Salable")
    sale_uom = fields.Many2One(
        'product.uom', "Sale UOM",
        states={
            'invisible': ~Eval('salable', False),
            'required': Eval('salable', False),
            },
        domain=[
            ('category', '=', Eval('default_uom_category')),
            ],
        depends=['salable', 'default_uom_category'])
    lead_time = fields.TimeDelta(
        "Lead Time",
        states={
            'invisible': ~Eval('salable', False),
            },
        depends=['salable'],
        help="The time from confirming the sales order to sending the "
        "products.\n"
        "If empty the default lead time from the configuration is used.")

    @classmethod
    def __register__(cls, module_name):
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        update = transaction.connection.cursor()
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()

        super(Template, cls).__register__(module_name)

        # Migration from 3.8: change delivery_time into timedelta lead_time
        if table.column_exist('delivery_time'):
            cursor.execute(*sql_table.select(
                    sql_table.id, sql_table.delivery_time))
            for id_, delivery_time in cursor:
                if delivery_time is None:
                    continue
                lead_time = datetime.timedelta(days=delivery_time)
                update.execute(*sql_table.update(
                        [sql_table.lead_time],
                        [lead_time],
                        where=sql_table.id == id_))
            table.drop_column('delivery_time')

    @fields.depends('default_uom', 'sale_uom', 'salable')
    def on_change_default_uom(self):
        try:
            super(Template, self).on_change_default_uom()
        except AttributeError:
            pass
        if self.default_uom:
            if self.sale_uom:
                if self.default_uom.category != self.sale_uom.category:
                    self.sale_uom = self.default_uom
            else:
                self.sale_uom = self.default_uom

    @classmethod
    def view_attributes(cls):
        return super(Template, cls).view_attributes() + [
            ('//page[@id="customers"]', 'states', {
                    'invisible': ~Eval('salable'),
                    })]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    sale_price_uom = fields.Function(Monetary(
            "Sale Price", digits=price_digits), 'get_sale_price_uom')

    @classmethod
    def get_sale_price_uom(cls, products, name):
        quantity = Transaction().context.get('quantity') or 0
        return cls.get_sale_price(products, quantity=quantity)

    def _get_sale_unit_price(self, quantity=0):
        return self.list_price_used

    @classmethod
    def get_sale_price(cls, products, quantity=0):
        '''
        Return the sale price for products and quantity.
        It uses if exists from the context:
            uom: the unit of measure or the sale uom of the product
            currency: the currency id for the returned price
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        User = pool.get('res.user')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        prices = {}

        assert len(products) == len(set(products)), "Duplicate products"

        uom = None
        if Transaction().context.get('uom'):
            uom = Uom(Transaction().context.get('uom'))

        currency = None
        if Transaction().context.get('currency'):
            currency = Currency(Transaction().context.get('currency'))

        user = User(Transaction().user)

        for product in products:
            unit_price = product._get_sale_unit_price(quantity=quantity)
            if unit_price is not None:
                if uom and product.default_uom.category == uom.category:
                    unit_price = Uom.compute_price(
                        product.default_uom, unit_price, uom)
                else:
                    unit_price = Uom.compute_price(
                        product.default_uom, unit_price, product.sale_uom)
            if currency and user.company and unit_price is not None:
                if user.company.currency != currency:
                    date = Transaction().context.get('sale_date') or today
                    with Transaction().set_context(date=date):
                        unit_price = Currency.compute(
                            user.company.currency, unit_price,
                            currency, round=False)
            prices[product.id] = unit_price
        return prices

    @property
    def lead_time_used(self):
        pool = Pool()
        Configuration = pool.get('product.configuration')
        if self.lead_time is None:
            with Transaction().set_context(self._context):
                config = Configuration(1)
                return config.get_multivalue('default_lead_time')
        else:
            return self.lead_time

    def compute_shipping_date(self, date=None):
        '''
        Compute the shipping date at the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            date = Date.today()

        lead_time = self.lead_time_used
        if lead_time is None:
            return datetime.date.max
        return date + lead_time


class SaleContext(ModelView):
    "Product Sale Context"
    __name__ = 'product.sale.context'

    locations = fields.Many2Many(
        'stock.location', None, None, "Warehouses",
        domain=[('type', '=', 'warehouse')])
    company = fields.Many2One('company.company', "Company")
    currency = fields.Many2One('currency.currency', "Currency")
    customer = fields.Many2One(
        'party.party', "Customer",
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    sale_date = fields.Date("Sale Date")
    quantity = fields.Float("Quantity")

    stock_date_end = fields.Function(
        fields.Date("Stock End Date"),
        'on_change_with_stock_date_end')

    @classmethod
    def default_locations(cls):
        pool = Pool()
        Location = pool.get('stock.location')
        locations = []
        warehouse = Location.get_default_warehouse()
        if warehouse:
            locations.append(warehouse)
        return locations

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_currency(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company_id = cls.default_company()
        if company_id:
            company = Company(company_id)
            return company.currency.id

    @fields.depends('sale_date')
    def on_change_with_stock_date_end(self, name=None):
        return self.sale_date
