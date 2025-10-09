# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
import os
import tempfile
from decimal import Decimal
from itertools import zip_longest
from unittest.mock import ANY, Mock, patch

from trytond.modules.account.tests import create_chart
from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.protocols.wrappers import HTTPStatus
from trytond.tests.test_tryton import (
    ModuleTestCase, RouteTestCase, with_transaction)


class WebShopProductDataFeedTestCase(ModuleTestCase):
    "Test Web Shop Product Data Feed module"
    module = 'web_shop_product_data_feed'
    extras = [
        'account_tax_rule_country',
        'product_image', 'product_kit', 'product_measurements',
        'sale_shipment_cost']

    @with_transaction()
    def test_data_feed(self):
        "Test data feed"
        pool = Pool()
        Account = pool.get('account.account')
        Carrier = pool.get('carrier')
        CarrierSelection = pool.get('carrier.selection')
        Country = pool.get('country.country')
        Party = pool.get('party.party')
        Product = pool.get('product.product')
        ProductCategory = pool.get('product.category')
        ProductIdentifier = pool.get('product.identifier')
        ProductTemplate = pool.get('product.template')
        Shop = pool.get('web.shop')
        Tax = pool.get('account.tax')
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

            create_chart(company)

            tax_account, = Account.search([
                    ('code', '=', '6.3.4'),
                    ])

            tax = Tax()
            tax.name = tax.description = 'Test'
            tax.type = 'percentage'
            tax.rate = Decimal('0.2')
            tax.invoice_account = tax_account
            tax.credit_note_account = tax_account
            tax.save()

            category = ProductCategory(
                name='Category', accounting=True,
                customer_taxes=[tax])
            category.save()

            carrier_template = ProductTemplate(
                name="Shipping",
                type='service',
                default_uom=unit,
                salable=True,
                sale_uom=unit,
                list_price=Decimal('5.0000'),
                account_category=category,
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

            with open(filename) as f1, \
                    open(os.path.join(
                            os.path.dirname(__file__),
                            'google-products.csv')) as f2:
                reader1 = csv.reader(f1, dialect=csv.excel_tab)
                reader2 = csv.reader(f2, dialect=csv.excel_tab)

                header1 = next(reader1)
                header2 = next(reader2)

                self.assertCountEqual(header1, header2)

                f1.seek(0)
                f2.seek(0)

                rows1 = csv.DictReader(f1, dialect=csv.excel_tab)
                rows2 = csv.DictReader(f2, dialect=csv.excel_tab)

                for i, (row1, row2) in enumerate(zip_longest(rows1, rows2)):
                    with self.subTest(row=i):
                        self.assertEqual(row1, row2)

            with patch.object(Shop, 'product_data_feed_csv') as feed:
                Shop.update_product_data_feed_csv()

                feed.assert_called_once_with(
                    'google', language=None, duration=ANY)


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
