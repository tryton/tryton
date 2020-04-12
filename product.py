# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def get_sale_price(cls, products, quantity=0):
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        Tax = pool.get('account.tax')
        context = Transaction().context

        prices = super(Product, cls).get_sale_price(products,
            quantity=quantity)
        if context.get('price_list'):
            price_list = PriceList(Transaction().context['price_list'])
            if context.get('customer'):
                customer = Party(context['customer'])
            else:
                customer = None
            context_uom = None
            if context.get('uom'):
                context_uom = Uom(Transaction().context['uom'])
            taxes = None
            if context.get('taxes'):
                taxes = Tax.browse(context.get('taxes'))
            for product in products:
                uom = context_uom or product.sale_uom
                if uom.category != product.sale_uom.category:
                    uom = product.sale_uom
                price = price_list.compute(
                     customer, product, prices[product.id], quantity, uom)
                if price_list.tax_included and taxes:
                    price = Tax.reverse_compute(price, taxes)
                prices[product.id] = price
        return prices


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
