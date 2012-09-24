#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['Product']
__metaclass__ = PoolMeta


class Product:
    __name__ = 'product.product'
    locations = fields.One2Many('stock.product.location', 'product',
        'Default Locations', states={
            'invisible': ~Eval('type').in_(['goods', 'assets']),
            })
