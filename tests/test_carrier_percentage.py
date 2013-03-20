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
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
    test_view, test_depends
from trytond.transaction import Transaction
from trytond.backend.sqlite.database import Database as SQLiteDatabase


class CarrierWeightTestCase(unittest.TestCase):
    '''
    Test CarrierWeight module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('carrier_percentage')
        self.party = POOL.get('party.party')
        self.uom = POOL.get('product.uom')
        self.template = POOL.get('product.template')
        self.product = POOL.get('product.product')
        self.category = POOL.get('product.category')
        self.currency = POOL.get('currency.currency')
        self.carrier = POOL.get('carrier')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('carrier_percentage')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010compute_percentage(self):
        '''
        Test compute_percentage.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            party, = self.party.create([{
                        'name': 'Carrier',
                        }])
            uom, = self.uom.search([
                    ('name', '=', 'Unit'),
                    ])
            category, = self.category.create([{
                        'name': 'Category',
                        }])
            template, = self.template.create([{
                        'name': 'Carrier',
                        'default_uom': uom.id,
                        'category': category.id,
                        'type': 'service',
                        'list_price': Decimal(0),
                        'cost_price': Decimal(0),
                        }])
            product, = self.product.create([{
                        'template': template.id,
                        }])
            currency, = self.currency.search([
                    ('code', '=', 'cu1'),
                    ])
            carrier, = self.carrier.create([{
                        'party': party.id,
                        'carrier_product': product.id,
                        'carrier_cost_method': 'percentage',
                        'percentage': Decimal(15),
                        }])
            for amount, price in [
                    (Decimal(0), Decimal(0)),
                    (Decimal(100), Decimal('15.00')),
                    (Decimal(150), Decimal('22.50')),
                    ]:
                self.assertEqual(
                    carrier.compute_percentage(amount, currency.id),
                    (price, currency.id))


def doctest_dropdb(test):
    '''
    Remove sqlite memory database
    '''
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    finally:
        cursor.close()


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.product.tests import test_product
    for test in test_product.suite():
        if test not in suite:
            suite.addTest(test)
    from trytond.modules.currency.tests import test_currency
    for test in test_currency.suite():
        if test not in suite:
            suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CarrierWeightTestCase))
    suite.addTests(doctest.DocFileSuite(
            'scenario_carrier_percentage_with_purchase_shipment_cost.rst',
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
