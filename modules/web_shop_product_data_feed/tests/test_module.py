# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os
import tempfile
from decimal import Decimal
from unittest.mock import Mock, patch

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.protocols.wrappers import HTTPStatus
from trytond.tests.test_tryton import (
    ModuleTestCase, RouteTestCase, with_transaction)


class WebShopProductDataFeedTestCase(ModuleTestCase):
    "Test Web Shop Product Data Feed module"
    module = 'web_shop_product_data_feed'
    extras = ['product_kit', 'product_measurements', 'sale_shipment_cost']

    @with_transaction()
    def test_data_feed(self):
        "Test data feed"
        pool = Pool()
        Carrier = pool.get('carrier')
        CarrierSelection = pool.get('carrier.selection')
        Country = pool.get('country.country')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        ProductIdentifier = pool.get('product.identifier')
        ProductTemplate = pool.get('product.template')
        Shop = pool.get('web.shop')
        UoM = pool.get('product.uom')

        unit, = UoM.search([('name', '=', "Unit")])
        meter, = UoM.search([('name', '=', "Meter")])
        cm, = UoM.search([('name', '=', "Centimeter")])
        kg, = UoM.search([('name', '=', "Kilogram")])
        country = Country(name="USA", code='US')
        country.save()
        company = create_company()
        with set_company(company), \
                patch.object(Shop, 'get_products') as get_products, \
                tempfile.TemporaryDirectory() as directory, \
                patch.object(tempfile, 'gettempdir') as gettempdir:
            gettempdir.return_value = directory

            carrier_template = ProductTemplate(
                name="Shipping",
                type='service',
                default_uom=unit,
                salable=True,
                sale_uom=unit,
                list_price=Decimal('5.0000'),
                )
            carrier_template.save()
            carrier_product = Product(template=carrier_template)
            carrier_product.save()

            carrier_party = Party(name="Carrier")
            carrier_party.save()
            carrier = Carrier(party=carrier_party)
            carrier.carrier_product = carrier_product
            carrier.save()
            CarrierSelection(carrier=carrier).save()

            template = ProductTemplate(
                name="Product",
                code="12345",
                type='goods',
                default_uom=unit,
                salable=True,
                sale_uom=unit,
                length=0.5,
                length_uom=meter,
                width=1,
                width_uom=meter,
                height=20,
                height_uom=cm,
                weight=5,
                weight_uom=kg,
                )
            template.save()
            product = Product(
                template=template,
                description="Description",
                )
            product.save()
            brand = ProductIdentifier(
                product=product, type='brand', code="Brand")
            brand.save()
            get_products.return_value = (
                [product], {product.id: Decimal('10.000')}, {})
            shop = Shop(name="Shop")
            shop.products = [product]
            shop.product_url_template = "https://example.com/p/${code}"
            shop.product_image_url_template = (
                "https://example.com/i/${code}.jpg")
            shop.countries = [country]
            shop.save()

            filename = shop.product_data_feed_csv('google')

            self.assertEqual(
                open(filename).read(),
                open(os.path.join(
                        os.path.dirname(__file__),
                        'google-products.csv')).read())


class WebShopProductDataFeedRouteTestCase(RouteTestCase):
    "Test Web Shop Product Data Feed route"
    module = 'web_shop_product_data_feed'

    @classmethod
    def setUpDatabase(cls):
        pool = Pool()
        cls.Shop = pool.get('web.shop')

    def test_data_feed(self):
        client = self.client()

        with patch.object(self.Shop, 'get') as get:
            get.return_value = shop = Mock(self.Shop)()
            response = client.get(
                f'/{self.db_name}/web_shop/1/google/products.csv')

            self.assertEqual(response.status_code, HTTPStatus.OK)
            shop.product_data_feed_csv.assert_called_once_with('google', None)


del ModuleTestCase
