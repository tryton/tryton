# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Template', 'Product']


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'
    landed_cost = fields.Boolean('Landed Cost', states={
            'readonly': ~Eval('active', True),
            'invisible': Eval('type') != 'service',
            }, depends=['active', 'type'])


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'
