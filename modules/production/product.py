# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.model.exceptions import RecursionError
from trytond.pool import PoolMeta
from trytond.pyson import Bool, Eval, Get, If, TimeDelta


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    producible = fields.Boolean("Producible")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.producible.states = {
            'invisible': ~Eval('type').in_(cls.get_producible_types()),
            }

    @classmethod
    def get_producible_types(cls):
        return ['goods', 'assets']

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[@id="production"]', 'states', {
                    'invisible': ~Eval('producible'),
                    })]


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    boms = fields.One2Many('product.product-production.bom', 'product',
        'BOMs', order=[('sequence', 'ASC'), ('id', 'ASC')],
        states={
            'invisible': ~Eval('producible')
            })
    production_lead_times = fields.One2Many('production.lead_time',
        'product', 'Lead Times', order=[('sequence', 'ASC'), ('id', 'ASC')],
        states={
            'invisible': ~Eval('producible'),
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
                if (input_.product == product
                        or input_.product.check_bom_recursion(
                            product=product)):
                    raise RecursionError(
                        gettext('production.msg_recursive_bom',
                            product=product.rec_name))

    @classmethod
    def copy(cls, products, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('boms', None)
        default.setdefault('production_lead_times', None)
        return super(Product, cls).copy(products, default=default)

    def get_bom(self, pattern=None):
        if pattern is None:
            pattern = {}
        for bom in self.boms:
            if bom.match(pattern):
                return bom


class ProductBom(sequence_ordered(), MatchMixin, ModelSQL, ModelView):
    'Product - BOM'
    __name__ = 'product.product-production.bom'

    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE', required=True,
        domain=[
            ('producible', '=', True),
            ])
    bom = fields.Many2One(
        'production.bom', "BOM", ondelete='CASCADE', required=True,
        domain=[
            ('output_products', '=', If(Bool(Eval('product')),
                    Eval('product', 0),
                    Get(Eval('_parent_product', {}), 'id', 0))),
            ])

    def get_rec_name(self, name):
        return self.bom.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('bom.rec_name',) + tuple(clause[1:])]


class ProductionLeadTime(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    'Production Lead Time'
    __name__ = 'production.lead_time'

    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE', required=True,
        domain=[
            ('producible', '=', True),
            ])
    bom = fields.Many2One('production.bom', 'BOM', ondelete='CASCADE',
        domain=[
            ('output_products', '=', If(Bool(Eval('product')),
                    Eval('product', -1),
                    Get(Eval('_parent_product', {}), 'id', 0))),
            ])
    lead_time = fields.TimeDelta(
        "Lead Time",
        domain=['OR',
            ('lead_time', '=', None),
            ('lead_time', '>=', TimeDelta()),
            ])

    @classmethod
    def __setup__(cls):
        super(ProductionLeadTime, cls).__setup__()
        cls._order.insert(0, ('product', 'ASC'))
