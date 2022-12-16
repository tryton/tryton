# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Case

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Get, If, Bool
from trytond.pool import PoolMeta

__all__ = ['Product', 'ProductBom']


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    boms = fields.One2Many('product.product-production.bom', 'product',
        'BOMs', order=[('sequence', 'ASC'), ('id', 'ASC')],
        states={
            'invisible': (Eval('type', 'service').in_(['service', None])
                & (Eval('_parent_template', {}).get(
                        'type', 'service').in_(['service', None]))),
            },
        depends=['type'])

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls._error_messages.update({
                'recursive_bom': ('You are trying to create a recursive BOM '
                    'with product "%s" which is not allowed.'),
                })

    @classmethod
    def validate(cls, products):
        super(Product, cls).validate(products)
        for product in products:
            product.check_bom_recursion()

    def check_bom_recursion(self, product=None):
        '''
        Check BOM recursion
        '''
        if product is None:
            product = self
        for product_bom in self.boms:
            for input_ in product_bom.bom.inputs:
                if (input_.product == product or
                        input_.product.check_bom_recursion(product=product)):
                    self.raise_user_error('recursive_bom', (product.rec_name,))

    @classmethod
    def copy(cls, products, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('boms', None)
        return super(Product, cls).copy(products, default=default)


class ProductBom(ModelSQL, ModelView):
    'Product - BOM'
    __name__ = 'product.product-production.bom'

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

    @classmethod
    def __setup__(cls):
        super(ProductBom, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    def get_rec_name(self, name):
        return self.bom.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('bom.rec_name',) + tuple(clause[1:])]

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]
