#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL
from trytond.transaction import Transaction
from trytond.pool import Pool


class Product(ModelSQL, ModelView):
    _name = 'product.product'

    def get_sale_price(self, ids, quantity=0):
        price_list_obj = Pool().get('product.price_list')

        res = super(Product, self).get_sale_price(ids, quantity=quantity)
        if (Transaction().context.get('price_list')
                and Transaction().context.get('customer')):
            for product in self.browse(ids):
                res[product.id] = price_list_obj.compute(
                        Transaction().context['price_list'],
                        Transaction().context['customer'],
                        product, res[product.id], quantity,
                        Transaction().context.get('uom', product.default_uom))
        return res

Product()
