# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond import backend

__all__ = ['Template', 'Product']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    salable = fields.Boolean('Salable', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])
    sale_uom = fields.Many2One('product.uom', 'Sale UOM', states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            'required': Eval('salable', False),
            },
        domain=[
            ('category', '=', Eval('default_uom_category')),
            ],
        depends=['active', 'salable', 'default_uom_category'])
    lead_time = fields.TimeDelta('Lead Time', states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            'required': Eval('salable', False),
            },
        depends=['active', 'salable'])

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        required = ~Eval('account_category', False) & Eval('salable', False)
        if not cls.account_revenue.states.get('required'):
            cls.account_revenue.states['required'] = required
        else:
            cls.account_revenue.states['required'] = (
                    cls.account_revenue.states['required'] | required)
        if 'account_category' not in cls.account_revenue.depends:
            cls.account_revenue.depends.append('account_category')
        if 'salable' not in cls.account_revenue.depends:
            cls.account_revenue.depends.append('salable')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()

        super(Template, cls).__register__(module_name)

        # Migration from 3.8: change delivery_time into timedelta lead_time
        if table.column_exist('delivery_time'):
            cursor.execute(*sql_table.select(
                    sql_table.id, sql_table.delivery_time))
            for id_, delivery_time in cursor.fetchall():
                if delivery_time is None:
                    continue
                lead_time = datetime.timedelta(days=delivery_time)
                cursor.execute(*sql_table.update(
                        [sql_table.lead_time],
                        [lead_time],
                        where=sql_table.id == id_))
            table.drop_column('delivery_time')

    @staticmethod
    def default_lead_time():
        return datetime.timedelta(0)

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


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    @staticmethod
    def get_sale_price(products, quantity=0):
        '''
        Return the sale price for products and quantity.
        It uses if exists from the context:
            uom: the unit of measure
            currency: the currency id for the returned price
        '''
        pool = Pool()
        Uom = pool.get('product.uom')
        User = pool.get('res.user')
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')

        today = Date.today()
        prices = {}

        uom = None
        if Transaction().context.get('uom'):
            uom = Uom(Transaction().context.get('uom'))

        currency = None
        if Transaction().context.get('currency'):
            currency = Currency(Transaction().context.get('currency'))

        user = User(Transaction().user)

        for product in products:
            prices[product.id] = product.list_price
            if uom:
                prices[product.id] = Uom.compute_price(
                    product.default_uom, prices[product.id], uom)
            if currency and user.company:
                if user.company.currency != currency:
                    date = Transaction().context.get('sale_date') or today
                    with Transaction().set_context(date=date):
                        prices[product.id] = Currency.compute(
                            user.company.currency, prices[product.id],
                            currency, round=False)
        return prices

    def compute_shipping_date(self, date=None):
        '''
        Compute the shipping date at the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            date = Date.today()
        return date + self.lead_time
