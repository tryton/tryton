#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import RPCProxy, CONTEXT, SOCK, test_view
from decimal import Decimal


class CurrencyTestCase(unittest.TestCase):
    '''
    Test Currency module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('currency')
        self.rate = RPCProxy('currency.currency.rate')
        self.currency = RPCProxy('currency.currency')
        self.date = RPCProxy('ir.date')

    def get_currency(self, code):
        return self.currency.search([
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
        cu1_id = self.currency.create({
            'name': 'cu1',
            'symbol': 'cu1',
            'code': 'cu1'
            }, CONTEXT)
        self.assert_(cu1_id)
        cu2_id = self.currency.create({
            'name': 'cu2',
            'symbol': 'cu2',
            'code': 'cu2'
            }, CONTEXT)
        self.assert_(cu2_id)

    def test0020mon_grouping(self):
        '''
        Check grouping
        '''
        cu1_id = self.get_currency('cu1')
        self.assertRaises(Exception, self.currency.write,
                cu1_id, {'mon_grouping': ''}, CONTEXT)

        self.assertRaises(Exception, self.currency.write,
                cu1_id, {'mon_grouping': '[a]'}, CONTEXT)

        self.assertRaises(Exception, self.currency.write,
                cu1_id, {'mon_grouping': '[1,"a"]'}, CONTEXT)

        self.assertRaises(Exception, self.currency.write,
                cu1_id, {'mon_grouping': '[1,"1"]'}, CONTEXT)

    def test0030rate(self):
        '''
        Create rates.
        '''
        cu1_id = self.get_currency('cu1')
        cu2_id = self.get_currency('cu2')

        rate1 = Decimal("1.3")
        rate1_id = self.rate.create({
            'rate': rate1,
            'currency': cu1_id,
            }, CONTEXT)
        self.assert_(rate1_id)

        rate2_id = self.rate.create({
            'rate': 1,
            'currency': cu2_id,
            }, CONTEXT)
        self.assert_(rate2_id)

        self.assertEqual(rate1, self.currency.read(
                cu1_id, ['rate'], CONTEXT)['rate'])

    def test0040rate_unicity(self):
        '''
        Rate unicity
        '''
        today = self.date.today(CONTEXT)

        cu_id = self.currency.create({
            'name': 'cu',
            'symbol': 'cu',
            'code': 'cu'
            }, CONTEXT)

        rate1_id = self.rate.create({
            'rate': 1.3,
            'currency': cu_id,
            'date': today,
            }, CONTEXT)

        self.assertRaises(Exception, self.rate.create, {
                'rate': 1.3,
                'currency': cu_id,
                'date': today,
                }, CONTEXT)

    def test0050compute_simple(self):
        '''
        Simple conversion
        '''
        cu1_id = self.get_currency('cu1')
        cu2_id = self.get_currency('cu2')

        amount = Decimal("10")
        expected = Decimal("13")
        converted_amount = self.currency.compute(
                cu2_id, amount, cu1_id, True, CONTEXT)
        self.assertEqual(converted_amount, expected)

    def test0060compute_nonfinite(self):
        '''
        Conversion with rounding on non-finite decimal representation
        '''
        cu1_id = self.get_currency('cu1')
        cu2_id = self.get_currency('cu2')

        amount = Decimal("10")
        expected = Decimal("7.69")
        converted_amount = self.currency.compute(
                cu1_id, amount, cu2_id, True, CONTEXT)
        self.assert_(converted_amount == expected)

    def test0070compute_nonfinite_worounding(self):
        '''
        Same without rounding
        '''
        cu1_id = self.get_currency('cu1')
        cu2_id = self.get_currency('cu2')

        amount = Decimal("10")
        expected = Decimal('7.692307692307692307692307692')
        converted_amount = self.currency.compute(
                cu1_id, amount, cu2_id, False, CONTEXT)
        self.assert_(converted_amount == expected)

    def test0080compute_same(self):
        '''
        Conversion to the same currency
        '''
        cu1_id = self.get_currency('cu1')

        amount = Decimal("10")
        converted_amount = self.currency.compute(
                cu1_id, amount, cu1_id, True, CONTEXT)
        self.assert_(converted_amount == amount)

    def test0090compute_zeroamount(self):
        '''
        Conversion with zero amount
        '''
        cu1_id = self.get_currency('cu1')
        cu2_id = self.get_currency('cu2')

        amount = Decimal("10")
        expected = Decimal("0")
        converted_amount = self.currency.compute(
                cu1_id, Decimal("0"), cu2_id, True, CONTEXT)
        self.assert_(converted_amount == expected)

    def test0100compute_zerorate(self):
        '''
        Conversion with zero rate
        '''
        cu1_id = self.get_currency('cu1')
        cu2_id = self.get_currency('cu2')

        rate_ids = self.rate.search([
                ('currency', '=', cu1_id),
                ], 0, 1, None, CONTEXT)
        self.rate.write(rate_ids, {
                'rate': 0,
                }, CONTEXT)
        amount = Decimal("10")
        self.assertRaises(Exception, self.currency.compute,
                cu1_id, amount, cu2_id, True, CONTEXT)
        self.assertRaises(Exception, self.currency.compute,
                cu2_id, amount, cu1_id, True, CONTEXT)

    def test0110compute_missingrate(self):
        '''
        Conversion with missing rate
        '''
        cu1_id = self.get_currency('cu1')
        cu3_id = self.currency.create({
            'name': 'cu3',
            'symbol': 'cu3',
            'code': 'cu3'
            }, CONTEXT)

        amount = Decimal("10")
        self.assertRaises(Exception, self.currency.compute,
                cu3_id, amount, cu1_id, True, CONTEXT)
        self.assertRaises(Exception, self.currency.compute,
                cu1_id, amount, cu3_id, True, CONTEXT)

    def test0120compute_bothmissingrate(self):
        '''
        Conversion with both missing rate
        '''
        cu3_id = self.get_currency('cu3')
        cu4_id = self.currency.create({
            'name': 'cu4',
            'symbol': 'cu4',
            'code': 'cu4'
            }, CONTEXT)

        amount = Decimal("10")
        self.assertRaises(Exception, self.currency.compute,
                cu3_id, amount, cu4_id, True, CONTEXT)

    def test0130delete_cascade(self):
        '''
        Test deletion of currency deletes rates
        '''
        codes = ['cu%s' % (i + 1) for i in range(4)]
        currency_ids = [self.get_currency(i) for i in codes]
        self.currency.delete(currency_ids, CONTEXT)

        rate_ids = self.rate.search([(
                'currency', 'in', currency_ids,
                )], 0, None, None, CONTEXT)
        self.assertFalse(rate_ids)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(CurrencyTestCase)

if __name__ == '__main__':
    suiteTrytond = trytond.tests.test_tryton.suite()
    suiteCurrency = suite()
    alltests = unittest.TestSuite([suiteTrytond, suiteCurrency])
    unittest.TextTestRunner(verbosity=2).run(alltests)
    SOCK.disconnect()
