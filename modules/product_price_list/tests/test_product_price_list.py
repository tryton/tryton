# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class ProductPriceListTestCase(ModuleTestCase):
    'Test ProductPriceList module'
    module = 'product_price_list'

    @with_transaction()
    def test_price_list(self):
        'Test price_list'
        pool = Pool()
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Party = pool.get('party.party')
        Uom = pool.get('product.uom')
        PriceList = pool.get('product.price_list')

        company = create_company()
        with set_company(company):
            party = Party(name='Customer')
            party.save()

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
            variant = Product(template=template)
            variant.save()

            price_list, = PriceList.create([{
                        'name': 'Default Price List',
                        'lines': [('create', [{
                                        'quantity': 10.0,
                                        'product': variant.id,
                                        'formula': 'unit_price * 0.8',
                                        }, {
                                        'quantity': 10.0,
                                        'formula': 'unit_price * 0.9',
                                        }, {
                                        'product': variant.id,
                                        'formula': 'unit_price * 1.1',
                                        }, {
                                        'formula': 'unit_price',
                                        }])],
                        }])
            tests = [
                (product, 1.0, kilogram, Decimal(10.0)),
                (product, 1000.0, gram, Decimal(10.0)),
                (variant, 1.0, kilogram, Decimal(11.0)),
                (product, 10.0, kilogram, Decimal(9.0)),
                (product, -10.0, kilogram, Decimal(9.0)),
                (product, 10000.0, gram, Decimal(9.0)),
                (variant, 10.0, kilogram, Decimal(8.0)),
                (variant, 10000.0, gram, Decimal(8.0)),
                ]
            for product, quantity, unit, result in tests:
                self.assertEqual(
                    price_list.compute(party, product, product.list_price,
                        quantity, unit),
                    result)

    @with_transaction()
    def test_price_list_category(self):
        "Test price list with category"
        pool = Pool()
        Category = pool.get('product.category')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        PriceList = pool.get('product.price_list')

        category = Category(name="Category")
        category.save()
        child_category = Category(name="Child Category", parent=category)
        child_category.save()

        unit, = Uom.search([('name', '=', 'Unit')])

        company = create_company()
        with set_company(company):
            template = Template(
                name="Template",
                list_price=Decimal(10),
                default_uom=unit,
                products=None,
                categories=[category],
                )
            template.save()
            product = Product(template=template)
            product.save()

            price_list, = PriceList.create([{
                        'name': "Price List",
                        'lines': [('create', [{
                                        'category': category.id,
                                        'formula': 'unit_price * 0.8',
                                        }, {
                                        'formula': 'unit_price',
                                        }])],
                        }])

            self.assertEqual(
                price_list.compute(None, product, product.list_price, 1, unit),
                Decimal(8))

            template.categories = []
            template.save()

            self.assertEqual(
                price_list.compute(None, product, product.list_price, 1, unit),
                Decimal(10))

            template.categories = [child_category]
            template.save()

            self.assertEqual(
                price_list.compute(None, product, product.list_price, 1, unit),
                Decimal(8))


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        ProductPriceListTestCase))
    return suite
