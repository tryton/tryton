#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class Product(ModelSQL, ModelView):
    _name = 'product.product'

    def get_sale_price(self, cursor, user, ids, quantity=0, context=None):
        price_list_obj = self.pool.get('product.price_list')

        if context is None:
            context = {}
        res = super(Product, self).get_sale_price(cursor, user, ids,
                quantity=quantity, context=context)
        if context.get('price_list') and context.get('customer'):
            for product in self.browse(cursor, user, ids, context=context):
                res[product.id] = price_list_obj.compute(cursor, user,
                        context['price_list'], context['customer'],
                        product, res[product.id], quantity,
                        context.get('uom', product.default_uom),
                        context=context)
        return res

Product()
