# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['ProductBom']


class ProductBom:
    __metaclass__ = PoolMeta
    __name__ = 'product.product-production.bom'
    routing = fields.Many2One('production.routing', 'Routing',
        ondelete='CASCADE', select=True,
        domain=[
            ('boms', '=', Eval('bom', 0)),
            ],
        depends=['bom'])
