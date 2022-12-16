# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    def _get_sale_unit_price(self, quantity=0):
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Tax = pool.get('account.tax')
        User = pool.get('res.user')
        context = Transaction().context

        unit_price = super()._get_sale_unit_price(quantity=quantity)

        if context.get('price_list'):
            price_list = PriceList(context['price_list'])
            assert price_list.company == User(Transaction().user).company
            if context.get('customer'):
                customer = Party(context['customer'])
            else:
                customer = None
            context_uom = None
            if context.get('uom'):
                context_uom = Uom(context['uom'])
            taxes = None
            if context.get('taxes'):
                taxes = Tax.browse(context.get('taxes'))
            uom = context_uom or self.sale_uom
            if uom.category != self.sale_uom.category:
                uom = self.sale_uom
            unit_price = price_list.compute(
                 customer, self, unit_price, quantity, uom)
            if price_list.tax_included and taxes:
                unit_price = Tax.reverse_compute(unit_price, taxes)
        return unit_price


class PriceList(metaclass=PoolMeta):
    __name__ = 'product.price_list'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.unit.selection.append(('product_sale', "Product Sale"))

    def get_uom(self, product):
        uom = super().get_uom(product)
        if self.unit == 'product_sale' and product.sale_uom:
            uom = product.sale_uom
        return uom


class SaleContext(metaclass=PoolMeta):
    __name__ = 'product.sale.context'

    price_list = fields.Many2One('product.price_list', "Price List")

    @classmethod
    def default_price_list(cls):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        config = Configuration(1)
        if config.sale_price_list:
            return config.sale_price_list.id

    @fields.depends('customer')
    def on_change_customer(self):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        try:
            super().on_change_customer()
        except AttributeError:
            pass
        if self.customer and self.customer.sale_price_list:
            self.price_list = self.customer.sale_price_list
        else:
            config = Configuration(1)
            self.price_list = config.sale_price_list
