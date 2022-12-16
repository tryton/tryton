# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

__all__ = ['register']

from . import web


def register():
    Pool.register(
        web.Shop,
        module='web_shop_vue_storefront_stripe', type_='model')
