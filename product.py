#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Get, If, Bool


class Product(ModelSQL, ModelView):
    _name = 'product.product'

    boms = fields.One2Many('product.product-production.bom', 'product',
        'BOMs', order=[('sequence', 'ASC'), ('id', 'ASC')],
        states={
            'invisible': Eval('type', 'service') == 'service',
            },
        depends=['type'])

    def __init__(self):
        super(Product, self).__init__()
        self._constraints += [
            ('check_bom_recursion', 'recursive_bom'),
        ]
        self._error_messages.update({
            'recursive_bom': 'You can not create recursive BOMs!',
        })

    def check_bom_recursion(self, ids):
        '''
        Check BOM recursion
        '''
        def check(sub_product, product):
            for product_bom in sub_product.boms:
                for input in product_bom.bom.inputs:
                    if input.product == product:
                        return False
                    if not check(input.product, product):
                        return False
            return True
        for product in self.browse(ids):
            if not check(product, product):
                return False
        return True

Product()


class ProductBom(ModelSQL, ModelView):
    'Product - BOM'
    _name = 'product.product-production.bom'
    _description = __doc__

    product = fields.Many2One('product.product', 'Product',
        ondelete='CASCADE', select=1, required=True,
        domain=[
            ('type', '!=', 'service'),
            ])
    bom = fields.Many2One('production.bom', 'BOM', ondelete='CASCADE',
        select=1, required=True, domain=[
            ('output_products', '=', If(Bool(Eval('product')),
                    Eval('product', 0),
                    Get(Eval('_parent_product', {}), 'id', 0))),
            ], depends=['product'])
    sequence = fields.Integer('Sequence')

    def __init__(self):
        super(ProductBom, self).__init__()
        self._order.insert(0, ('sequence', 'ASC'))

    def get_rec_name(self, ids, name):
        result = {}
        for product_bom in self.browse(ids):
            result[product_bom.id] = product_bom.bom.rec_name
        return result

    def search_rec_name(self, name, clause):
        return [('bom.rec_name',) + clause[1:]]

ProductBom()
