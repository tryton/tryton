#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import logging
logging.basicConfig(level=logging.FATAL)

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB, USER, CONTEXT, test_view
from decimal import Decimal


class CurrencyTestCase(unittest.TestCase):
    '''
    Test Currency module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('currency')
        self.rate = POOL.get('currency.currency.rate')
        self.currency = POOL.get('currency.currency')
        self.date = POOL.get('ir.date')

    def get_currency(self, cursor, code):
        return self.currency.search(cursor, USER, [
                ('code', '=', code),
                ], 0, 1, None, CONTEXT)[0]

    def test0005views(self):
        '''
        Test views.
        '''
        self.assertRaises(Exception, test_view('currency'))

    def test0010currencies(self):
        '''
        Create currencies
        '''
        cursor = DB.cursor()

        cu1_id = self.currency.create(cursor, USER, {
            'name': 'cu1',
            'symbol': 'cu1',
            'code': 'cu1'
            }, CONTEXT)
        self.assert_(cu1_id)

        cu2_id = self.currency.create(cursor, USER, {
            'name': 'cu2',
            'symbol': 'cu2',
            'code': 'cu2'
            }, CONTEXT)
        self.assert_(cu2_id)

        cursor.commit()
        cursor.close()

    def test0020mon_grouping(self):
        '''
        Check grouping
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')

        self.assertRaises(Exception, self.currency.write, cursor, USER,
                cu1_id, {'mon_grouping': ''}, CONTEXT)

        self.assertRaises(Exception, self.currency.write, cursor, USER,
                cu1_id, {'mon_grouping': '[a]'}, CONTEXT)

        self.assertRaises(Exception, self.currency.write, cursor, USER,
                cu1_id, {'mon_grouping': '[1,"a"]'}, CONTEXT)

        self.assertRaises(Exception, self.currency.write, cursor, USER,
                cu1_id, {'mon_grouping': '[1,"1"]'}, CONTEXT)

        cursor.close()

    def test0030rate(self):
        '''
        Create rates.
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu2_id = self.get_currency(cursor, 'cu2')

        rate1 = Decimal("1.3")
        rate1_id = self.rate.create(cursor, USER, {
            'rate': rate1,
            'currency': cu1_id,
            }, CONTEXT)
        self.assert_(rate1_id)

        rate2_id = self.rate.create(cursor, USER, {
            'rate': Decimal("1"),
            'currency': cu2_id,
            }, CONTEXT)
        self.assert_(rate2_id)

        self.assertEqual(rate1, self.currency.read(cursor, USER,
                cu1_id, ['rate'], CONTEXT)['rate'])

        cursor.commit()
        cursor.close()

    def test0040rate_unicity(self):
        '''
        Rate unicity
        '''
        cursor = DB.cursor()
        today = self.date.today(cursor, USER, CONTEXT)

        cu_id = self.currency.create(cursor, USER, {
            'name': 'cu',
            'symbol': 'cu',
            'code': 'cu'
            }, CONTEXT)

        rate1_id = self.rate.create(cursor, USER, {
            'rate': Decimal("1.3"),
            'currency': cu_id,
            'date': today,
            }, CONTEXT)

        self.assertRaises(Exception, self.rate.create, cursor, USER, {
                'rate': Decimal("1.3"),
                'currency': cu_id,
                'date': today,
                }, CONTEXT)

        cursor.rollback()
        cursor.close()

    def test0050compute_simple(self):
        '''
        Simple conversion
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu2_id = self.get_currency(cursor, 'cu2')

        amount = Decimal("10")
        expected = Decimal("13")
        converted_amount = self.currency.compute(cursor, USER,
                cu2_id, amount, cu1_id, True, CONTEXT)
        self.assertEqual(converted_amount, expected)

        cursor.commit()
        cursor.close()

    def test0060compute_nonfinite(self):
        '''
        Conversion with rounding on non-finite decimal representation
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu2_id = self.get_currency(cursor, 'cu2')

        amount = Decimal("10")
        expected = Decimal("7.69")
        converted_amount = self.currency.compute(cursor, USER,
                cu1_id, amount, cu2_id, True, CONTEXT)
        self.assert_(converted_amount == expected)

        cursor.close()

    def test0070compute_nonfinite_worounding(self):
        '''
        Same without rounding
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu2_id = self.get_currency(cursor, 'cu2')

        amount = Decimal("10")
        expected = Decimal('7.692307692307692307692307692')
        converted_amount = self.currency.compute(cursor, USER,
                cu1_id, amount, cu2_id, False, CONTEXT)
        self.assert_(converted_amount == expected)

        cursor.close()

    def test0080compute_same(self):
        '''
        Conversion to the same currency
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')

        amount = Decimal("10")
        converted_amount = self.currency.compute(cursor, USER,
                cu1_id, amount, cu1_id, True, CONTEXT)
        self.assert_(converted_amount == amount)

        cursor.close()

    def test0090compute_zeroamount(self):
        '''
        Conversion with zero amount
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu2_id = self.get_currency(cursor, 'cu2')

        amount = Decimal("10")
        expected = Decimal("0")
        converted_amount = self.currency.compute(cursor, USER,
                cu1_id, Decimal("0"), cu2_id, True, CONTEXT)
        self.assert_(converted_amount == expected)

        cursor.close()

    def test0100compute_zerorate(self):
        '''
        Conversion with zero rate
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu2_id = self.get_currency(cursor, 'cu2')

        rate_ids = self.rate.search(cursor, USER, [
                ('currency', '=', cu1_id),
                ], 0, 1, None, CONTEXT)
        self.rate.write(cursor, USER, rate_ids, {
                'rate': Decimal("0"),
                }, CONTEXT)
        amount = Decimal("10")
        self.assertRaises(Exception, self.currency.compute,
                cu1_id, amount, cu2_id, True, CONTEXT)
        self.assertRaises(Exception, self.currency.compute,
                cu2_id, amount, cu1_id, True, CONTEXT)

        cursor.rollback()
        cursor.close()

    def test0110compute_missingrate(self):
        '''
        Conversion with missing rate
        '''
        cursor = DB.cursor()
        cu1_id = self.get_currency(cursor, 'cu1')
        cu3_id = self.currency.create(cursor, USER, {
            'name': 'cu3',
            'symbol': 'cu3',
            'code': 'cu3'
            }, CONTEXT)

        amount = Decimal("10")
        self.assertRaises(Exception, self.currency.compute, cursor, USER,
                cu3_id, amount, cu1_id, True, CONTEXT)
        self.assertRaises(Exception, self.currency.compute, cursor, USER,
                cu1_id, amount, cu3_id, True, CONTEXT)

        cursor.rollback()
        cursor.close()

    def test0120compute_bothmissingrate(self):
        '''
        Conversion with both missing rate
        '''
        cursor = DB.cursor()
        cu3_id = self.currency.create(cursor, USER, {
            'name': 'cu3',
            'symbol': 'cu3',
            'code': 'cu3'
            }, CONTEXT)
        cu4_id = self.currency.create(cursor, USER, {
            'name': 'cu4',
            'symbol': 'cu4',
            'code': 'cu4'
            }, CONTEXT)

        amount = Decimal("10")
        self.assertRaises(Exception, self.currency.compute, cursor, USER,
                cu3_id, amount, cu4_id, True, CONTEXT)

        cursor.rollback()
        cursor.close()

    def test0130delete_cascade(self):
        '''
        Test deletion of currency deletes rates
        '''
        cursor = DB.cursor()
        codes = ['cu%s' % (i + 1) for i in range(2)]
        currency_ids = [self.get_currency(cursor, i) for i in codes]
        self.currency.delete(cursor, USER, currency_ids, CONTEXT)

        rate_ids = self.rate.search(cursor, USER, [(
                'currency', 'in', currency_ids,
                )], 0, None, None, CONTEXT)
        self.assertFalse(rate_ids)

        cursor.rollback()
        cursor.close()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(CurrencyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
