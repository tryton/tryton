# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, sale

__all__ = ['register']


def register():
    Pool.register(
        product.Template,
        product.Product,
        sale.Line,
        module='sale_product_quantity', type_='model')
    Pool.register(
        sale.POSLine,
        module='sale_product_quantity', type_='model', depends=['sale_point'])
