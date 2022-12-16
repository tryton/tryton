# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['Template', 'Product']


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'
    _history = True


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'
    _history = True
