# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['ProductBom', 'ProductionLeadTime']


class ProductBom(metaclass=PoolMeta):
    __name__ = 'product.product-production.bom'
    routing = fields.Many2One('production.routing', 'Routing',
        ondelete='CASCADE', select=True,
        domain=[
            ('boms', '=', Eval('bom', 0)),
            ],
        depends=['bom'])


class ProductionLeadTime(metaclass=PoolMeta):
    __name__ = 'production.lead_time'
    routing = fields.Many2One('production.routing', 'Routing',
        ondelete='CASCADE',
        domain=[
            ('boms', '=', Eval('bom', 0)),
            ],
        depends=['bom'])
