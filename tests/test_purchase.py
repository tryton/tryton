# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import doctest
from decimal import Decimal

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.transaction import Transaction


class PurchaseTestCase(ModuleTestCase):
    'Test Purchase module'
    module = 'purchase'

    def test_purchase_price(self):
        'Test purchase price'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            Company = POOL.get('company.company')
            User = POOL.get('res.user')
            Account = POOL.get('account.account')
            Template = POOL.get('product.template')
            Product = POOL.get('product.product')
            Uom = POOL.get('product.uom')
            ProductSupplier = POOL.get('purchase.product_supplier')
            Party = POOL.get('party.party')

            company, = Company.search([('rec_name', '=', 'Dunder Mifflin')])
            User.write([User(USER)], {
                    'main_company': company.id,
                    'company': company.id,
                    })

            receivable, = Account.search([
                    ('kind', '=', 'receivable'),
                    ('company', '=', company.id),
                    ])
            payable, = Account.search([
                    ('kind', '=', 'payable'),
                    ('company', '=', company.id),
                    ])

            kg, = Uom.search([('name', '=', 'Kilogram')])
            g, = Uom.search([('name', '=', 'Gram')])

            template, = Template.create([{
                        'name': 'Product',
                        'default_uom': g.id,
                        'purchase_uom': kg.id,
                        'list_price': Decimal(5),
                        'cost_price': Decimal(2),
                        'products': [('create', [{}])],
                        }])
            product, = template.products

            supplier, = Party.create([{
                        'name': 'Supplier',
                        'account_receivable': receivable.id,
                        'account_payable': payable.id,
                        }])
            product_supplier, = ProductSupplier.create([{
                        'product': template.id,
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


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        PurchaseTestCase))
    suite.addTests(doctest.DocFileSuite('scenario_purchase.rst',
            setUp=doctest_setup, tearDown=doctest_teardown, encoding='UTF-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite
