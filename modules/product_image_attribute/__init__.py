# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product

__all__ = ['register']


def register():
    Pool.register(
        product.Product,
        product.Image,
        module='product_image_attribute', type_='model')
