#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view
from trytond.transaction import Transaction


class CurrencyTestCase(unittest.TestCase):
    '''
    Test Currency module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('currency')
        self.rate = POOL.get('currency.currency.rate')
        self.currency = POOL.get('currency.currency')
        self.date = POOL.get('ir.date')

    def get_currency(self, code):
        return self.currency.search([
            ('code', '=', code),
            ], limit=1)[0]

    def test0005views(self):
        '''
        Test views.
        '''
        self.assertRaises(Exception, test_view('currency'))

    def test0010currencies(self):
        '''
        Create currencies
        '''

        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.currency.create({
                'name': 'cu1',
                'symbol': 'cu1',
                'code': 'cu1'
                })
            self.assert_(cu1_id)

            cu2_id = self.currency.create({
                'name': 'cu2',
                'symbol': 'cu2',
                'code': 'cu2'
                })
            self.assert_(cu2_id)

            transaction.cursor.commit()

    def test0020mon_grouping(self):
        '''
        Check grouping
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')

            self.assertRaises(Exception, self.currency.write, cu1_id, 
                {'mon_grouping': ''})

            self.assertRaises(Exception, self.currency.write, cu1_id, 
                {'mon_grouping': '[a]'})

            self.assertRaises(Exception, self.currency.write, cu1_id, 
                {'mon_grouping': '[1,"a"]'})

            self.assertRaises(Exception, self.currency.write, cu1_id, 
                {'mon_grouping': '[1,"1"]'})

    def test0030rate(self):
        '''
        Create rates.
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu2_id = self.get_currency('cu2')

            rate1 = Decimal("1.3")
            rate1_id = self.rate.create({
                'rate': rate1,
                'currency': cu1_id,
                })
            self.assert_(rate1_id)

            rate2_id = self.rate.create({
                'rate': Decimal("1"),
                'currency': cu2_id,
                })
            self.assert_(rate2_id)

            self.assertEqual(rate1, self.currency.read(cu1_id, 
                ['rate'])['rate'])

            transaction.cursor.commit()

    def test0040rate_unicity(self):
        '''
        Rate unicity
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            today = self.date.today()

            cu_id = self.currency.create({
                'name': 'cu',
                'symbol': 'cu',
                'code': 'cu'
                })

            rate1_id = self.rate.create({
                'rate': Decimal("1.3"),
                'currency': cu_id,
                'date': today,
                })

            self.assertRaises(Exception, self.rate.create, {
                    'rate': Decimal("1.3"),
                    'currency': cu_id,
                    'date': today,
                    })

            transaction.cursor.rollback()

    def test0050compute_simple(self):
        '''
        Simple conversion
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu2_id = self.get_currency('cu2')

            amount = Decimal("10")
            expected = Decimal("13")
            converted_amount = self.currency.compute(
                    cu2_id, amount, cu1_id, True)
            self.assertEqual(converted_amount, expected)

            transaction.cursor.commit()

    def test0060compute_nonfinite(self):
        '''
        Conversion with rounding on non-finite decimal representation
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu2_id = self.get_currency('cu2')

            amount = Decimal("10")
            expected = Decimal("7.69")
            converted_amount = self.currency.compute(
                    cu1_id, amount, cu2_id, True)
            self.assert_(converted_amount == expected)

    def test0070compute_nonfinite_worounding(self):
        '''
        Same without rounding
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu2_id = self.get_currency('cu2')

            amount = Decimal("10")
            expected = Decimal('7.692307692307692307692307692')
            converted_amount = self.currency.compute(
                    cu1_id, amount, cu2_id, False)
            self.assert_(converted_amount == expected)

    def test0080compute_same(self):
        '''
        Conversion to the same currency
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
    
            amount = Decimal("10")
            converted_amount = self.currency.compute(
                    cu1_id, amount, cu1_id, True)
            self.assert_(converted_amount == amount)

    def test0090compute_zeroamount(self):
        '''
        Conversion with zero amount
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu2_id = self.get_currency('cu2')
    
            amount = Decimal("10")
            expected = Decimal("0")
            converted_amount = self.currency.compute(
                    cu1_id, Decimal("0"), cu2_id, True)
            self.assert_(converted_amount == expected)

    def test0100compute_zerorate(self):
        '''
        Conversion with zero rate
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu2_id = self.get_currency('cu2')
    
            rate_ids = self.rate.search([
                    ('currency', '=', cu1_id),
                    ], 0, 1, None)
            self.rate.write(rate_ids, {
                    'rate': Decimal("0"),
                    })
            amount = Decimal("10")
            self.assertRaises(Exception, self.currency.compute,
                cu1_id, amount, cu2_id, True)
            self.assertRaises(Exception, self.currency.compute,
                    cu2_id, amount, cu1_id, True)

            transaction.cursor.rollback()

    def test0110compute_missingrate(self):
        '''
        Conversion with missing rate
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu1_id = self.get_currency('cu1')
            cu3_id = self.currency.create({
                'name': 'cu3',
                'symbol': 'cu3',
                'code': 'cu3'
                })
    
            amount = Decimal("10")
            self.assertRaises(Exception, self.currency.compute,
                    cu3_id, amount, cu1_id, True)
            self.assertRaises(Exception, self.currency.compute, 
                    cu1_id, amount, cu3_id, True)
    
            transaction.cursor.rollback()

    def test0120compute_bothmissingrate(self):
        '''
        Conversion with both missing rate
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            cu3_id = self.currency.create({
                'name': 'cu3',
                'symbol': 'cu3',
                'code': 'cu3'
                })
            cu4_id = self.currency.create({
                'name': 'cu4',
                'symbol': 'cu4',
                'code': 'cu4'
                })
    
            amount = Decimal("10")
            self.assertRaises(Exception, self.currency.compute,
                    cu3_id, amount, cu4_id, True)
    
            transaction.cursor.rollback()

    def test0130delete_cascade(self):
        '''
        Test deletion of currency deletes rates
        '''
        with Transaction().start(DB_NAME, USER, CONTEXT) as transaction:
            codes = ['cu%s' % (i + 1) for i in range(2)]
            currency_ids = [self.get_currency(i) for i in codes]
            self.currency.delete(currency_ids)
    
            rate_ids = self.rate.search([(
                    'currency', 'in', currency_ids,
                    )], 0, None, None)
            self.assertFalse(rate_ids)
    
            transaction.cursor.rollback()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(CurrencyTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
