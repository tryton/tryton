# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends, test_menu_action
from trytond.transaction import Transaction


class CurrencyTestCase(unittest.TestCase):
    'Test Currency module'

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
        'Test views'
        test_view('currency')

    def test0006depends(self):
        'Test depends'
        test_depends()

    def test0007menu_actions(self):
        'Test menu actions'
        test_menu_action('currency')

    def test0010currencies(self):
        'Create currencies'

        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cu1, cu2 = self.currency.create([{
                        'name': 'cu1',
                        'symbol': 'cu1',
                        'code': 'cu1'
                        }, {
                        'name': 'cu2',
                        'symbol': 'cu2',
                        'code': 'cu2'
                        }])
            self.assert_(cu1)
            self.assert_(cu2)

            transaction.cursor.commit()

    def test0020mon_grouping(self):
        'Check grouping'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            cu1 = self.get_currency('cu1')

            self.assertRaises(Exception, self.currency.write, [cu1],
                {'mon_grouping': ''})

            self.assertRaises(Exception, self.currency.write, [cu1],
                {'mon_grouping': '[a]'})

            self.assertRaises(Exception, self.currency.write, [cu1],
                {'mon_grouping': '[1,"a"]'})

            self.assertRaises(Exception, self.currency.write, [cu1],
                {'mon_grouping': '[1,"1"]'})

    def test0030rate(self):
        'Create rates'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cu1 = self.get_currency('cu1')
            cu2 = self.get_currency('cu2')

            rate1, rate2 = self.rate.create([{
                        'rate': Decimal("1.3"),
                        'currency': cu1.id,
                        }, {
                        'rate': Decimal("1"),
                        'currency': cu2.id,
                        }])
            self.assert_(rate1)
            self.assert_(rate2)

            self.assertEqual(cu1.rate, Decimal("1.3"))

            transaction.cursor.commit()

    def test0040rate_unicity(self):
        'Rate unicity'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            today = self.date.today()

            cu, = self.currency.create([{
                        'name': 'cu',
                        'symbol': 'cu',
                        'code': 'cu'
                        }])

            self.rate.create([{
                        'rate': Decimal("1.3"),
                        'currency': cu.id,
                        'date': today,
                        }])

            self.assertRaises(Exception, self.rate.create, {
                    'rate': Decimal("1.3"),
                    'currency': cu.id,
                    'date': today,
                    })

            transaction.cursor.rollback()

    def test0050compute_simple(self):
        'Simple conversion'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cu1 = self.get_currency('cu1')
            cu2 = self.get_currency('cu2')

            amount = Decimal("10")
            expected = Decimal("13")
            converted_amount = self.currency.compute(
                cu2, amount, cu1, True)
            self.assertEqual(converted_amount, expected)

            transaction.cursor.commit()

    def test0060compute_nonfinite(self):
        'Conversion with rounding on non-finite decimal representation'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            cu1 = self.get_currency('cu1')
            cu2 = self.get_currency('cu2')

            amount = Decimal("10")
            expected = Decimal("7.69")
            converted_amount = self.currency.compute(
                cu1, amount, cu2, True)
            self.assertEqual(converted_amount, expected)

    def test0070compute_nonfinite_worounding(self):
        'Same without rounding'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            cu1 = self.get_currency('cu1')
            cu2 = self.get_currency('cu2')

            amount = Decimal("10")
            expected = Decimal('7.692307692307692307692307692')
            converted_amount = self.currency.compute(
                cu1, amount, cu2, False)
            self.assertEqual(converted_amount, expected)

    def test0080compute_same(self):
        'Conversion to the same currency'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            cu1 = self.get_currency('cu1')

            amount = Decimal("10")
            converted_amount = self.currency.compute(
                cu1, amount, cu1, True)
            self.assertEqual(converted_amount, amount)

    def test0090compute_zeroamount(self):
        'Conversion with zero amount'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            cu1 = self.get_currency('cu1')
            cu2 = self.get_currency('cu2')

            expected = Decimal("0")
            converted_amount = self.currency.compute(
                cu1, Decimal("0"), cu2, True)
            self.assertEqual(converted_amount, expected)

    def test0100compute_zerorate(self):
        'Conversion with zero rate'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cu1 = self.get_currency('cu1')
            cu2 = self.get_currency('cu2')

            rates = self.rate.search([
                    ('currency', '=', cu1.id),
                    ], 0, 1, None)
            self.rate.write(rates, {
                    'rate': Decimal("0"),
                    })
            amount = Decimal("10")
            self.assertRaises(Exception, self.currency.compute,
                cu1, amount, cu2, True)
            self.assertRaises(Exception, self.currency.compute,
                cu2, amount, cu1, True)

            transaction.cursor.rollback()

    def test0110compute_missingrate(self):
        'Conversion with missing rate'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cu1 = self.get_currency('cu1')
            cu3, = self.currency.create([{
                        'name': 'cu3',
                        'symbol': 'cu3',
                        'code': 'cu3'
                        }])

            amount = Decimal("10")
            self.assertRaises(Exception, self.currency.compute,
                cu3, amount, cu1, True)
            self.assertRaises(Exception, self.currency.compute,
                cu1, amount, cu3, True)

            transaction.cursor.rollback()

    def test0120compute_bothmissingrate(self):
        'Conversion with both missing rate'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            cu3, cu4 = self.currency.create([{
                        'name': 'cu3',
                        'symbol': 'cu3',
                        'code': 'cu3'
                        }, {
                        'name': 'cu4',
                        'symbol': 'cu4',
                        'code': 'cu4'
                        }])

            amount = Decimal("10")
            self.assertRaises(Exception, self.currency.compute,
                cu3, amount, cu4, True)

            transaction.cursor.rollback()

    def test0130delete_cascade(self):
        'Test deletion of currency deletes rates'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            codes = ['cu%s' % (i + 1) for i in range(2)]
            currencies = [self.get_currency(i) for i in codes]
            self.currency.delete(currencies)

            rates = self.rate.search([(
                        'currency', 'in', map(int, currencies),
                        )], 0, None, None)
            self.assertFalse(rates)

            transaction.cursor.rollback()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CurrencyTestCase))
    return suite
