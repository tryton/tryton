# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from decimal import Decimal

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company


class ProductPriceListParentTestCase(ModuleTestCase):
    'Test Product Price List Parent module'
    module = 'product_price_list_parent'

    @with_transaction()
    def test_price_list_parent(self):
        "Test price list with parent"
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

            unit, = Uom.search([('name', '=', "Unit")])

            template = Template(
                name="Template", list_price=Decimal(10), default_uom=unit)
            template.save()
            product = Product(template=template)
            product.save()

            price_list_parent, = PriceList.create([{
                        'name': "Parent",
                        'lines': [('create', [{
                                        'formula': 'unit_price * 2',
                                        }])],
                        }])
            price_list, = PriceList.create([{
                        'name': "List",
                        'parent': price_list_parent.id,
                        'lines': [('create', [{
                                        'formula': 'parent_unit_price * 2',
                                        }])],
                        }])

            self.assertEqual(
                price_list.compute(
                    party, product, product.list_price, 1, unit),
                Decimal('40'))

    @with_transaction()
    def test_line_formula_help(self):
        "Test help of line formula"
        pool = Pool()
        PriceListLine = pool.get('product.price_list.line')

        fields = PriceListLine.fields_get(['formula'])

        self.assertIn('parent_unit_price', fields['formula']['help'])


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProductPriceListParentTestCase))
    return suite
