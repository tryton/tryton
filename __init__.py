# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import routes

__all__ = ['register', 'routes']

from . import carrier
from . import ir
from . import party
from . import product
from . import sale
from . import web


def register():
    Pool.register(
        web.Shop,
        web.ShopVSFIdentifier,
        web.User,
        ir.Cron,
        party.Address,
        party.Identifier,
        product.Product,
        product.Template,
        product.Category,
        sale.Sale,
        sale.Line,
        module='web_shop_vue_storefront', type_='model')
    Pool.register(
        product.ProductAttribute,
        product.TemplateAttribute,
        product.Attribute,
        sale.LineAttribute,
        module='web_shop_vue_storefront', type_='model',
        depends=['product_attribute'])
    Pool.register(
        web.ShopCoupon,
        module='web_shop_vue_storefront', type_='model',
        depends=['sale_promotion_coupon'])
    Pool.register(
        carrier.Carrier,
        module='web_shop_vue_storefront', type_='model',
        depends=['carrier'])
    Pool.register(
        web.ShopShipmentCost,
        sale.SaleShipmentCost,
        module='web_shop_vue_storefront', type_='model',
        depends=['sale_shipment_cost'])
