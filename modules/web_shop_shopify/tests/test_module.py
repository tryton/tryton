# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.party.tests import PartyCheckReplaceMixin
from trytond.tests.test_tryton import ModuleTestCase


class WebShopShopifyTestCase(PartyCheckReplaceMixin, ModuleTestCase):
    'Test Web Shop Shopify module'
    module = 'web_shop_shopify'
    extras = [
        'customs', 'product_image', 'product_image_attribute',
        'product_measurements', 'sale_discount', 'sale_invoice_grouping',
        'sale_secondary_unit', 'sale_shipment_cost', 'stock_package_shipping']


del ModuleTestCase
