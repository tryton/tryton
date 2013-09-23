#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import datetime

from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Template', 'Product']
__metaclass__ = PoolMeta


class Template:
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
        on_change_with=['default_uom', 'sale_uom', 'salable'],
        depends=['active', 'salable', 'default_uom_category'])
    delivery_time = fields.Integer('Delivery Time', states={
            'readonly': ~Eval('active', True),
            'invisible': ~Eval('salable', False),
            'required': Eval('salable', False),
            },
        depends=['active', 'salable'],
        help='In number of days')

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

    @staticmethod
    def default_delivery_time():
        return 0

    def on_change_with_sale_uom(self):
        if self.default_uom:
            if self.sale_uom:
                if self.default_uom.category == self.sale_uom.category:
                    return self.sale_uom.id
                else:
                    return self.default_uom.id
            else:
                return self.default_uom.id


class Product:
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

    def compute_delivery_date(self, date=None):
        '''
        Compute the delivery date a the given date
        '''
        Date = Pool().get('ir.date')

        if not date:
            date = Date.today()
        return date + datetime.timedelta(self.delivery_time)
