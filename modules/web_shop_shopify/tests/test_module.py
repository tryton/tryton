# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.party.tests import PartyCheckReplaceMixin
from trytond.modules.web_shop_shopify.common import gid2id, id2gid
from trytond.tests.test_tryton import ModuleTestCase


class WebShopShopifyTestCase(PartyCheckReplaceMixin, ModuleTestCase):
    'Test Web Shop Shopify module'
    module = 'web_shop_shopify'
    extras = [
        'carrier', 'customs', 'product_image', 'product_image_attribute',
        'product_kit', 'product_measurements', 'sale_discount',
        'sale_invoice_grouping', 'sale_secondary_unit', 'sale_shipment_cost',
        'stock_package_shipping']

    def test_id2gid(self):
        "Test ID to GID"
        self.assertEqual(id2gid('Product', '123'), 'gid://shopify/Product/123')

    def test_gid2id(self):
        "Test GID to ID"
        self.assertEqual(gid2id('gid://shopify/Product/123'), 123)


del ModuleTestCase
