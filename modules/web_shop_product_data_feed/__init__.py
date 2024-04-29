# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import product, routes, web

__all__ = ['register', 'routes']


def register():
    Pool.register(
        product.UoM,
        product.Template,
        product.Product,
        product.CategoryGoogle,
        product.CategoryFacebook,
        web.Shop,
        module='web_shop_product_data_feed', type_='model')
    Pool.register(
        web.Shop_Kit,
        module='web_shop_product_data_feed', type_='model',
        depends=['product_kit'])
    Pool.register(
        web.Shop_Measurement,
        module='web_shop_product_data_feed', type_='model',
        depends=['product_measurements'])
    Pool.register(
        web.Shop_ShipmentCost,
        module='web_shop_product_data_feed', type_='model',
        depends=['sale_shipment_cost'])
    Pool.register(
        web.Shop_TaxRuleCountry,
        module='web_shop_product_data_feed', type_='model',
        depends=['account_tax_rule_country'])
