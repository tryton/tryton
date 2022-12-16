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


class PurchaseTestCase(ModuleTestCase):
    'Test Purchase module'
    module = 'purchase'

    @with_transaction()
    def test_purchase_price(self):
        'Test purchase price'
        pool = Pool()
        Account = pool.get('account.account')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')
        ProductSupplier = pool.get('purchase.product_supplier')
        Party = pool.get('party.party')

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

            template, = Template.create([{
                        'name': 'Product',
                        'default_uom': g.id,
                        'purchase_uom': kg.id,
                        'list_price': Decimal(5),
                        'products': [('create', [{
                                        'cost_price': Decimal(2),
                                        }])],
                        }])
            product, = template.products

            supplier, = Party.create([{
                        'name': 'Supplier',
                        'account_receivable': receivable.id,
                        'account_payable': payable.id,
                        }])
            product_supplier, = ProductSupplier.create([{
                        'template': template.id,
                        'party': supplier.id,
                        'prices': [('create', [{
                                        'sequence': 1,
                                        'quantity': 1,
                                        'unit_price': Decimal(3000),
                                        }, {
                                        'sequence': 2,
                                        'quantity': 2,
                                        'unit_price': Decimal(2500),
                                        }])],
                        }])

            prices = Product.get_purchase_price([product], quantity=100)
            self.assertEqual(prices, {product.id: Decimal(2)})
            prices = Product.get_purchase_price([product], quantity=1500)
            self.assertEqual(prices, {product.id: Decimal(2)})

            with Transaction().set_context(uom=kg.id):
                prices = Product.get_purchase_price([product], quantity=0.5)
                self.assertEqual(prices, {product.id: Decimal(2000)})
                prices = Product.get_purchase_price([product], quantity=1.5)
                self.assertEqual(prices, {product.id: Decimal(2000)})

            with Transaction().set_context(supplier=supplier.id):
                prices = Product.get_purchase_price([product], quantity=100)
                self.assertEqual(prices, {product.id: Decimal(2)})
                prices = Product.get_purchase_price([product], quantity=1500)
                self.assertEqual(prices, {product.id: Decimal(3)})
                prices = Product.get_purchase_price([product], quantity=3000)
                self.assertEqual(prices, {product.id: Decimal('2.5')})

            with Transaction().set_context(uom=kg.id, supplier=supplier.id):
                prices = Product.get_purchase_price([product], quantity=0.5)
                self.assertEqual(prices, {product.id: Decimal(2000)})
                prices = Product.get_purchase_price([product], quantity=1.5)
                self.assertEqual(prices, {product.id: Decimal(3000)})
                prices = Product.get_purchase_price([product], quantity=3)
                self.assertEqual(prices, {product.id: Decimal(2500)})
                prices = Product.get_purchase_price([product], quantity=-4)
                self.assertEqual(prices, {product.id: Decimal(2500)})


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        PurchaseTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_purchase.rst',
            tearDown=doctest_teardown, encoding='UTF-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite('scenario_purchase_empty.rst',
            tearDown=doctest_teardown, encoding='UTF-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite(
            'scenario_purchase_modify_header.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite(
            'scenario_purchase_return_wizard.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    suite.addTests(doctest.DocFileSuite(
            'scenario_purchase_copy_product_suppliers.rst',
            tearDown=doctest_teardown, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE,
            checker=doctest_checker))
    return suite
