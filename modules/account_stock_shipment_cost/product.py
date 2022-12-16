# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    shipment_cost = fields.Boolean(
        "Shipment Cost",
        states={
            'invisible': Eval('type') != 'service',
            },
        depends=['type'])


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
