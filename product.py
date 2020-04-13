# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.supply_on_sale.states['invisible'] &= (
            ~Eval('producible') | ~Eval('salable'))
        cls.supply_on_sale.depends.extend(['producible', 'salable'])


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
