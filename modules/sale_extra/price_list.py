# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['PriceList']
__metaclass__ = PoolMeta


class PriceList:
    __name__ = 'product.price_list'

    sale_extras = fields.One2Many('sale.extra', 'price_list', 'Sale Extras')
