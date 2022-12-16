# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['Template', 'Product', 'TemplateLotType']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'

    # TODO to replace with a Multiple Selection
    lot_required = fields.Many2Many('product.template-stock.lot.type',
        'template', 'type', 'Lot Required',
        help='The type of location for which lot is required',
        states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            },
        depends=['type'])


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'

    def lot_is_required(self, from_, to):
        'Is product lot required for move with "from_" and "to" location ?'
        lot_required = [t.code for t in self.lot_required]
        for location in (from_, to):
            if location.type in lot_required:
                return True


class TemplateLotType(ModelSQL):
    'Template - Stock Lot Type'
    __name__ = 'product.template-stock.lot.type'

    template = fields.Many2One('product.template', 'Template', required=True,
        select=True, ondelete='CASCADE')
    type = fields.Many2One('stock.lot.type', 'Type', required=True,
        ondelete='CASCADE')
