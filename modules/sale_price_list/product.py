#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    __name__ = 'product.product'

    @classmethod
    def get_sale_price(cls, products, quantity=0):
        pool = Pool()
        PriceList = pool.get('product.price_list')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')

        prices = super(Product, cls).get_sale_price(products,
            quantity=quantity)
        if (Transaction().context.get('price_list')
                and Transaction().context.get('customer')):
            price_list = PriceList(Transaction().context['price_list'])
            customer = Party(Transaction().context['customer'])
            context_uom = None
            if Transaction().context.get('uom'):
                context_uom = Uom(Transaction().context['uom'])
            for product in products:
                uom = context_uom or product.default_uom
                prices[product.id] = price_list.compute(customer, product,
                    prices[product.id], quantity, uom)
        return prices
