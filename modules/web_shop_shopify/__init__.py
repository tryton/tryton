# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    account, ir, party, product, routes, sale, shopify_retry, stock, web)

__all__ = ['register', 'routes']

shopify_retry.patch()


def register():
    Pool.register(
        ir.Cron,
        web.Shop,
        web.ShopShopifyIdentifier,
        web.Shop_Warehouse,
        web.Shop_Attribute,
        web.ShopShopifyPaymentJournal,
        product.Category,
        product.TemplateCategory,
        product.Template,
        product.Product,
        product.ShopifyInventoryItem,
        product.ProductIdentifier,
        product.AttributeSet,
        product.Attribute,
        party.Party,
        party.Address,
        sale.Sale,
        sale.Line,
        account.Payment,
        account.PaymentJournal,
        stock.ShipmentOut,
        stock.ShipmentShopifyIdentifier,
        stock.Move,
        module='web_shop_shopify', type_='model')
    Pool.register(
        product.ShopifyInventoryItem_Customs,
        product.Product_TariffCode,
        module='web_shop_shopify', type_='model', depends=['customs'])
    Pool.register(
        product.Image,
        module='web_shop_shopify', type_='model', depends=['product_image'])
    Pool.register(
        product.Image_Attribute,
        module='web_shop_shopify', type_='model',
        depends=['product_attribute', 'product_image_attribute'])
    Pool.register(
        sale.Line_Discount,
        module='web_shop_shopify', type_='model', depends=['sale_discount'])
    Pool.register(
        product.Template_SaleSecondaryUnit,
        product.Product_SaleSecondaryUnit,
        sale.Line_SaleSecondaryUnit,
        module='web_shop_shopify', type_='model',
        depends=['sale_secondary_unit'])
    Pool.register(
        sale.Sale_ShipmentCost,
        sale.Line_ShipmentCost,
        module='web_shop_shopify', type_='model',
        depends=['sale_shipment_cost'])
    Pool.register(
        stock.ShipmentOut_PackageShipping,
        module='web_shop_shopify', type_='model',
        depends=['stock_package_shipping'])
    Pool.register(
        party.Replace,
        module='web_shop_shopify', type_='wizard')
