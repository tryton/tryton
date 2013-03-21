#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import doctest
import datetime
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


class StockSupplyDayTestCase(unittest.TestCase):
    '''
    Test StockSupplyDay module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('stock_supply_day')
        self.uom = POOL.get('product.uom')
        self.uom_category = POOL.get('product.uom.category')
        self.category = POOL.get('product.category')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.company = POOL.get('company.company')
        self.party = POOL.get('party.party')
        self.account = POOL.get('account.account')
        self.product_supplier = POOL.get('purchase.product_supplier')
        self.product_supplier_day = POOL.get('purchase.product_supplier.day')
        self.user = POOL.get('res.user')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('stock_supply_day')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010compute_supply_date(self):
        '''
        Test compute_supply_date.
        '''
        dates = [
            # purchase date, delivery time, weekday, supply date
            (datetime.date(2011, 11, 21), 10, 0, datetime.date(2011, 12, 5)),
            (datetime.date(2011, 11, 21), 9, 1, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 21), 8, 2, datetime.date(2011, 11, 30)),
            (datetime.date(2011, 11, 21), 7, 3, datetime.date(2011, 12, 1)),
            (datetime.date(2011, 11, 21), 6, 4, datetime.date(2011, 12, 2)),
            (datetime.date(2011, 11, 21), 5, 5, datetime.date(2011, 11, 26)),
            (datetime.date(2011, 11, 21), 4, 6, datetime.date(2011, 11, 27)),
            (datetime.date(2011, 12, 22), 12, 6, datetime.date(2012, 1, 8)),
            (datetime.date(2011, 11, 21), 10, None,
                datetime.date(2011, 12, 1)),
            ]
            # Purchase date is Monday, 2011-11-21, the regular days to deliver
            # is 10 days, which would be Wednesday 2011-12-01. But with the
            # supplier weekday 0 (Monday) the forecast supply date is next
            # Monday, the 2011-12-05.
        for purchase_date, delivery_time, weekday, supply_date in dates:
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                product_supplier = self.create_product_supplier_day(
                    delivery_time, weekday)
                date = product_supplier.compute_supply_date(purchase_date)
                self.assertEqual(date, supply_date)

    def test0020compute_purchase_date(self):
        '''
        Test compute_purchase_date.
        '''
        dates = [
            # purchase date, delivery time, weekday, supply date
            (datetime.date(2011, 11, 25), 10, 0, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 27), 9, 1, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 22), 8, 2, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 24), 7, 3, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 26), 6, 4, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 28), 5, 5, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 11, 30), 4, 6, datetime.date(2011, 12, 6)),
            (datetime.date(2011, 12, 27), 6, 0, datetime.date(2012, 1, 3)),
            ]
            # Supply date max is Tuesday, 2012-01-03, the supplier weekday 0
            # which would be Monday 2012-01-02. But with the 6 days of delivery
            # the forecast purchase date is the 2011-12-27.
        for purchase_date, delivery_time, weekday, supply_date in dates:
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                product_supplier = self.create_product_supplier_day(
                    delivery_time, weekday)
                date = product_supplier.compute_purchase_date(supply_date)
                self.assertEqual(date, purchase_date)

    def create_product_supplier_day(self, delivery_time, weekday):
        '''
        Create a Product with a Product Supplier Day

        :param delivery_time: minimal time in days needed to supply
        :param weekday: supply day of the week (0 - 6)
        :return: the id of the Product Supplier Day
        '''
        uom_category, = self.uom_category.create([{'name': 'Test'}])
        uom, = self.uom.create([{
                    'name': 'Test',
                    'symbol': 'T',
                    'category': uom_category.id,
                    'rate': 1.0,
                    'factor': 1.0,
                    }])
        category, = self.category.create([{'name': 'ProdCategoryTest'}])
        template, = self.template.create([{
                    'name': 'ProductTest',
                    'default_uom': uom.id,
                    'category': category.id,
                    'account_category': True,
                    'list_price': Decimal(0),
                    'cost_price': Decimal(0),
                    }])
        product, = self.product.create([{
                    'template': template.id,
                    }])
        company, = self.company.search([('rec_name', '=', 'B2CK')])
        self.user.write([self.user(USER)], {
            'main_company': company.id,
            'company': company.id,
            })
        receivable, = self.account.search([
            ('kind', '=', 'receivable'),
            ('company', '=', company.id),
            ])
        payable, = self.account.search([
            ('kind', '=', 'payable'),
            ('company', '=', company.id),
            ])
        supplier, = self.party.create([{
                    'name': 'supplier',
                    'account_receivable': receivable.id,
                    'account_payable': payable.id,
                    }])
        product_supplier, = self.product_supplier.create([{
                    'product': template.id,
                    'company': company.id,
                    'party': supplier.id,
                    'delivery_time': delivery_time,
                    }])
        if weekday is not None:
            self.product_supplier_day.create([{
                        'product_supplier': product_supplier.id,
                        'weekday': str(weekday),
                        }])
        return product_supplier


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        if test not in suite:
            suite.addTest(test)
    from trytond.modules.account.tests import test_account
    for test in test_account.suite():
        if test not in suite and not isinstance(test, doctest.DocTestCase):
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        StockSupplyDayTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
