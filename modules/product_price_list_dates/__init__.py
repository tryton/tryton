# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, purchase, sale

__all__ = ['register']


def register():
    Pool.register(
        product.PriceList,
        product.PriceListLine,
        product.PriceListLineContext,
        module='product_price_list_dates', type_='model')
    Pool.register(
        product.PriceListCache,
        module='product_price_list_dates', type_='model',
        depends=['product_price_list_cache'])
    Pool.register(
        sale.Line,
        product.SaleContext,
        module='product_price_list_dates', type_='model',
        depends=['sale_price_list'])
    Pool.register(
        purchase.Line,
        module='product_price_list_dates', type_='model',
        depends=['purchase_price_list'])
