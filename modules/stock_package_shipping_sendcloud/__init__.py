# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.stock_package_shipping.stock import ShippingMixin
from trytond.pool import Pool

from . import carrier, stock

__all__ = ['register']


def register():
    Pool.register(
        carrier.CredentialSendcloud,
        carrier.SendcloudAddress,
        carrier.SendcloudShippingMethod,
        carrier.Carrier,
        stock.Package,
        module='stock_package_shipping_sendcloud', type_='model')
    Pool.register(
        stock.CreateShipping,
        stock.CreateShippingSendcloud,
        module='stock_package_shipping_sendcloud', type_='wizard')
    Pool.register_mixin(
        stock.ShippingSendcloudMixin, ShippingMixin,
        module='stock_package_shipping_sendcloud')
