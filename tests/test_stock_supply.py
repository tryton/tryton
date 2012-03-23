#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction

DATES = [
    # purchase date, delivery time, supply date
    (datetime.date(2011, 11, 21), 10, datetime.date(2011, 12, 1)),
    (datetime.date(2011, 11, 21), 9, datetime.date(2011, 11, 30)),
    (datetime.date(2011, 11, 21), 8, datetime.date(2011, 11, 29)),
    (datetime.date(2011, 11, 21), 7, datetime.date(2011, 11, 28)),
    (datetime.date(2011, 11, 21), 6, datetime.date(2011, 11, 27)),
    (datetime.date(2011, 11, 21), 5, datetime.date(2011, 11, 26)),
    (datetime.date(2011, 11, 21), 4, datetime.date(2011, 11, 25)),
    ]


class StockSupplyTestCase(unittest.TestCase):
    '''
    Test StockSupply module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_supply')
        self.uom = POOL.get('product.uom')
        self.uom.category = POOL.get('product.uom.category')
        self.category = POOL.get('product.category')
        self.product = POOL.get('product.product')
        self.company = POOL.get('company.company')
        self.party = POOL.get('party.party')
        self.account = POOL.get('account.account')
        self.product_supplier = POOL.get('purchase.product_supplier')
        self.user = POOL.get('res.user')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('stock_supply')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010compute_supply_date(self):
        '''
        Test compute_supply_date.
        '''
        for purchase_date, delivery_time, supply_date in DATES:
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                product_supplier_id = self.create_product_supplier(
                    delivery_time)
                product_supplier = self.product_supplier.browse(
                    product_supplier_id)
                date = self.product_supplier.compute_supply_date(
                    product_supplier, purchase_date)
                self.assertEqual(date, supply_date)

    def test0020compute_purchase_date(self):
        '''
        Test compute_purchase_date.
        '''
        for purchase_date, delivery_time, supply_date in DATES:
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                product_supplier_id = self.create_product_supplier(
                    delivery_time)
                product_supplier = self.product_supplier.browse(
                    product_supplier_id)
                date = self.product_supplier.compute_purchase_date(
                    product_supplier, supply_date)
                self.assertEqual(date, purchase_date)

    def create_product_supplier(self, delivery_time):
        '''
        Create a Product with a Product Supplier

        :param delivery_time: time in days needed to supply
        :return: the id of the Product Supplier
        '''
        uom_category_id = self.uom.category.create({'name': 'Test'})
        uom_id = self.uom.create({
            'name': 'Test',
            'symbol': 'T',
            'category': uom_category_id,
            'rate': 1.0,
            'factor': 1.0,
            })
        category_id = self.category.create({'name': 'ProdCategoryTest'})
        product_id = self.product.create({
                'name': 'ProductTest',
                'default_uom': uom_id,
                'category': category_id,
                'account_category': True,
                'list_price': Decimal(0),
                'cost_price': Decimal(0),
                })
        company_id, = self.company.search([('name', '=', 'B2CK')])
        self.user.write(USER, {
            'main_company': company_id,
            'company': company_id,
            })
        receivable_id, = self.account.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company_id),
            ])
        payable_id, = self.account.search([
            ('kind', '=', 'payable'),
            ('company', '=', company_id),
            ])
        supplier_id = self.party.create({
            'name': 'supplier',
            'account_receivable': receivable_id,
            'account_payable': payable_id,
            })
        product_supplier_id = self.product_supplier.create({
            'product': product_id,
            'company': company_id,
            'party': supplier_id,
            'delivery_time': delivery_time,
            })
        return product_supplier_id


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockSupplyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
