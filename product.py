# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Template']


class Template:
    __name__ = 'product.template'
    __metaclass__ = PoolMeta
    landed_cost = fields.Boolean('Landed Cost', states={
            'readonly': ~Eval('active', True),
            'invisible': Eval('type') != 'service',
            }, depends=['active', 'type'])
