# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest
from decimal import Decimal
import trytond.tests.test_tryton
from trytond.transaction import Transaction
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool


def create_currency(name):
    pool = Pool()
    Currency = pool.get('currency.currency')
    return Currency.create([{
                'name': name,
                'symbol': name,
                'code': name,
                }])[0]


def add_currency_rate(currency, rate, date=None):
    pool = Pool()
    Rate = pool.get('currency.currency.rate')
    if date is None:
        date = Rate.default_date()
    return Rate.create([{
                'currency': currency.id,
                'rate': rate,
                'date': date,
                }])[0]


class CurrencyTestCase(ModuleTestCase):
    'Test Currency module'
    module = 'currency'

    def get_currency(self, code):
        return self.currency.search([
            ('code', '=', code),
            ], limit=1)[0]

    @with_transaction()
    def test_currencies(self):
        'Create currencies'
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')
        self.assert_(cu1)
        self.assert_(cu2)

    @with_transaction()
    def test_rate(self):
        'Create rates'
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')

        rate1 = add_currency_rate(cu1, Decimal("1.3"))
        rate2 = add_currency_rate(cu2, Decimal("1"))
        self.assert_(rate1)
        self.assert_(rate2)

        self.assertEqual(cu1.rate, Decimal("1.3"))

    @with_transaction()
    def test_rate_unicity(self):
        'Rate unicity'
        pool = Pool()
        Rate = pool.get('currency.currency.rate')
        Date = pool.get('ir.date')
        today = Date.today()

        cu = create_currency('cu')

        Rate.create([{
                    'rate': Decimal("1.3"),
                    'currency': cu.id,
                    'date': today,
                    }])

        self.assertRaises(Exception, Rate.create, {
                'rate': Decimal("1.3"),
                'currency': cu.id,
                'date': today,
                })

    @with_transaction()
    def test_compute_simple(self):
        'Simple conversion'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')
        add_currency_rate(cu1, Decimal("1.3"))
        add_currency_rate(cu2, Decimal("1"))

        amount = Decimal("10")
        expected = Decimal("13")
        converted_amount = Currency.compute(
            cu2, amount, cu1, True)
        self.assertEqual(converted_amount, expected)

    @with_transaction()
    def test_compute_nonfinite(self):
        'Conversion with rounding on non-finite decimal representation'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')
        add_currency_rate(cu1, Decimal("1.3"))
        add_currency_rate(cu2, Decimal("1"))

        amount = Decimal("10")
        expected = Decimal("7.69")
        converted_amount = Currency.compute(
            cu1, amount, cu2, True)
        self.assertEqual(converted_amount, expected)

    @with_transaction()
    def test_compute_nonfinite_worounding(self):
        'Same without rounding'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')
        add_currency_rate(cu1, Decimal("1.3"))
        add_currency_rate(cu2, Decimal("1"))

        amount = Decimal("10")
        expected = Decimal('7.692307692307692307692307692')
        converted_amount = Currency.compute(
            cu1, amount, cu2, False)
        self.assertEqual(converted_amount, expected)

    @with_transaction()
    def test_compute_same(self):
        'Conversion to the same currency'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        add_currency_rate(cu1, Decimal("1.3"))

        amount = Decimal("10")
        converted_amount = Currency.compute(
            cu1, amount, cu1, True)
        self.assertEqual(converted_amount, amount)

    @with_transaction()
    def test_compute_zeroamount(self):
        'Conversion with zero amount'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')
        add_currency_rate(cu1, Decimal("1.3"))
        add_currency_rate(cu2, Decimal("1"))

        expected = Decimal("0")
        converted_amount = Currency.compute(
            cu1, Decimal("0"), cu2, True)
        self.assertEqual(converted_amount, expected)

    @with_transaction()
    def test_compute_zerorate(self):
        'Conversion with zero rate'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')

        add_currency_rate(cu1, Decimal('0'))
        add_currency_rate(cu2, Decimal('1'))

        amount = Decimal("10")
        self.assertRaises(Exception, Currency.compute,
            cu1, amount, cu2, True)
        self.assertRaises(Exception, Currency.compute,
            cu2, amount, cu1, True)

    @with_transaction()
    def test_compute_missingrate(self):
        'Conversion with missing rate'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu1 = create_currency('cu1')
        cu3 = create_currency('cu3')
        add_currency_rate(cu1, Decimal("1.3"))

        amount = Decimal("10")
        self.assertRaises(Exception, Currency.compute,
            cu3, amount, cu1, True)
        self.assertRaises(Exception, Currency.compute,
            cu1, amount, cu3, True)

    @with_transaction()
    def test_compute_bothmissingrate(self):
        'Conversion with both missing rate'
        pool = Pool()
        Currency = pool.get('currency.currency')
        cu3 = create_currency('cu3')
        cu4 = create_currency('cu4')

        amount = Decimal("10")
        self.assertRaises(Exception, Currency.compute,
            cu3, amount, cu4, True)

    @with_transaction()
    def test_delete_cascade(self):
        'Test deletion of currency deletes rates'
        pool = Pool()
        Currency = pool.get('currency.currency')
        Rate = pool.get('currency.currency.rate')
        currencies = [create_currency('cu%s' % i) for i in range(3)]
        [add_currency_rate(c, Decimal('1')) for c in currencies]
        Currency.delete(currencies)

        rates = Rate.search([(
                    'currency', 'in', map(int, currencies),
                    )], 0, None, None)
        self.assertFalse(rates)

    @with_transaction()
    def test_currency_rate_sql(self):
        "Test currency rate SQL"
        pool = Pool()
        Currency = pool.get('currency.currency')
        transaction = Transaction()
        cursor = transaction.connection.cursor()
        date = datetime.date

        cu1 = create_currency('cu1')
        for date_, rate in [
                (date(2017, 1, 1), Decimal(1)),
                (date(2017, 2, 1), Decimal(2)),
                (date(2017, 3, 1), Decimal(3))]:
            add_currency_rate(cu1, rate, date_)
        cu2 = create_currency('cu2')
        for date_, rate in [
                (date(2017, 2, 1), Decimal(2)),
                (date(2017, 4, 1), Decimal(4))]:
            add_currency_rate(cu2, rate, date_)

        query = Currency.currency_rate_sql()
        cursor.execute(*query)
        data = set(cursor.fetchall())
        result = {
            (cu1.id, Decimal(1), date(2017, 1, 1), date(2017, 2, 1)),
            (cu1.id, Decimal(2), date(2017, 2, 1), date(2017, 3, 1)),
            (cu1.id, Decimal(3), date(2017, 3, 1), None),
            (cu2.id, Decimal(2), date(2017, 2, 1), date(2017, 4, 1)),
            (cu2.id, Decimal(4), date(2017, 4, 1), None),
            }

        self.assertSetEqual(data, result)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            CurrencyTestCase))
    return suite
