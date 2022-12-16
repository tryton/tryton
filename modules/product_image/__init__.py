# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        product.Template,
        product.Product,
        product.Image,
        product.ImageCache,
        module='product_image', type_='model')
    Pool.register(
        module='product_image', type_='wizard')
    Pool.register(
        module='product_image', type_='report')
