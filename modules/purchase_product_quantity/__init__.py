# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, purchase

__all__ = ['register']


def register():
    Pool.register(
        product.ProductSupplier,
        module='purchase_product_quantity', type_='model')
    Pool.register(
        purchase.RequestCreatePurchase,
        module='purchase_product_quantity', type_='wizard')
