# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_teardown, doctest_checker
from trytond.transaction import Transaction
from trytond.pool import Pool

from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart


class SaleTestCase(ModuleTestCase):
    'Test Sale module'
    module = 'sale'

    @with_transaction()
    def test_sale_price(self):
        "Test sale price"
        pool = Pool()
        Account = pool.get('account.account')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        company = create_company()
        with set_company(company):
            create_chart(company)

            receivable, = Account.search([
                    ('type.receivable', '=', True),
                    ('company', '=', company.id),
                    ])
            payable, = Account.search([
                    ('type.payable', '=', True),
                    ('company', '=', company.id),
                    ])

            kg, = Uom.search([('name', '=', 'Kilogram')])
            g, = Uom.search([('name', '=', 'Gram')])
            pound, = Uom.search([('name', '=', 'Pound')])

            template, = Template.create([{
                        'name': 'Product',
                        'default_uom': g.id,
                        'sale_uom': kg.id,
                        'list_price': Decimal(5),
                        'products': [('create', [{}])],
                        }])
            product, = template.products

            prices = Product.get_sale_price([product], quantity=100)
            self.assertEqual(prices, {product.id: Decimal(5000)})
            prices = Product.get_sale_price([product], quantity=1500)
            self.assertEqual(prices, {product.id: Decimal(5000)})

            with Transaction().set_context(uom=pound.id):
                prices = Product.get_sale_price([product], quantity=0.5)
                self.assertEqual(prices, {product.id: Decimal('2267.96185')})
                prices = Product.get_sale_price([product], quantity=1.5)
                self.assertEqual(prices, {product.id: Decimal('2267.96185')})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(SaleTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_sale.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite('scenario_sale_empty.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_modify_header.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite(
            'scenario_sale_reporting.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    return suite
