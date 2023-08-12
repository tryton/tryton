# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal
from unittest.mock import patch

from trytond.modules.company.tests import create_company, set_company
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductPriceListCacheTestCase(ModuleTestCase):
    "Test Product Price List Cache module"
    module = 'product_price_list_cache'

    @with_transaction()
    def test_price_list_cache(self):
        "Test caching price list"
        pool = Pool()
        Cache = pool.get('product.price_list.cache')
        PriceList = pool.get('product.price_list')
        Product = pool.get('product.product')
        Template = pool.get('product.template')
        Uom = pool.get('product.uom')

        company = create_company()
        with set_company(company):
            kilogram, = Uom.search([
                    ('name', '=', 'Kilogram'),
                    ])
            gram, = Uom.search([
                    ('name', '=', 'Gram'),
                    ])

            template = Template(
                name='Test Lot Sequence',
                list_price=Decimal(10),
                default_uom=kilogram,
                )
            template.save()
            product = Product(template=template)
            product.save()

            price_list, = PriceList.create([{
                        'name': "Price List",
                        'price': 'list_price',
                        'lines': [('create', [{
                                        'quantity': 10.0,
                                        'formula': 'unit_price * 0.9',
                                        }, {
                                        'quantity': 5,
                                        'formula': 'unit_price',
                                        }, {
                                        'formula': 'unit_price',
                                        }])],
                        }])

            # Test filling cache
            price_list.fill_cache()
            self.assertEqual(Cache.search([], count=True), 1)

            price_list.fill_cache(products=[product])
            self.assertEqual(Cache.search([], count=True), 1)

            PriceList.fill_cache(products=[product])
            self.assertEqual(Cache.search([], count=True), 1)

            PriceList.fill_cache()
            self.assertEqual(Cache.search([], count=True), 1)

            cache, = Cache.search([])
            self.assertEqual(cache.price_list, price_list)
            self.assertEqual(cache.product, product)
            self.assertEqual(cache.uom, kilogram)
            self.assertEqual(
                cache.unit_prices, [[0, Decimal(10)], [10, Decimal(9)]])
            self.assertEqual(cache.pattern, None)

            # Test cached compute
            with patch.object(
                    Cache, 'get',
                    side_effect=Cache.get) as get, \
                    patch.object(
                        Cache, 'get_unit_price',
                        autospec=True,
                        side_effect=Cache.get_unit_price) as get_unit_price:
                self.assertEqual(
                    price_list.compute(product, 1, kilogram),
                    Decimal(10))
                get.assert_called_once()
                get_unit_price.assert_called_once()

                get_unit_price.return_value = None
                get_unit_price.reset_mock()
                self.assertEqual(
                    price_list.compute(product, 1, kilogram),
                    Decimal(10))
                get_unit_price.assert_called_once()

                get.return_value = None
                get.side_effect = None
                get.reset_mock()
                get_unit_price.reset_mock()
                self.assertEqual(
                    price_list.compute(product, 1, kilogram),
                    Decimal(10))
                get.assert_called_once()
                get_unit_price.assert_not_called()

            # test get
            self.assertEqual(Cache.get(price_list, product), cache)
            self.assertEqual(
                Cache.get(price_list, product, pattern={'foo': 'bar'}), None)

            # Test get_unit_price
            for quantity, uom, result in [
                    (1, kilogram, Decimal(10)),
                    (1_000, gram, Decimal(10)),
                    (2, kilogram, Decimal(10)),
                    (2_000, gram, Decimal(10)),
                    (10, kilogram, Decimal(9)),
                    (10_000, gram, Decimal(9)),
                    (11, kilogram, Decimal(9)),
                    (11_000, gram, Decimal(9)),
                    ]:
                with self.subTest(quantity=quantity, uom=uom.rec_name):
                    self.assertEqual(
                        cache.get_unit_price(quantity, uom), result)


del ModuleTestCase
