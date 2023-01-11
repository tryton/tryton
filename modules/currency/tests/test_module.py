# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import unittest
from decimal import ROUND_HALF_DOWN, Decimal

from trytond import backend
from trytond.modules.currency.ecb import (
    RatesNotAvailableError, UnsupportedCurrencyError, get_rates)
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction


def create_currency(name):
    pool = Pool()
    Currency = pool.get('currency.currency')
    return Currency.create([{
                'name': name,
                'symbol': name,
                'code': name,
                }])[0]


def add_currency_rate(currency, rate, date=datetime.date.min):
    pool = Pool()
    Rate = pool.get('currency.currency.rate')
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
        self.assertTrue(cu1)
        self.assertTrue(cu2)

    @with_transaction()
    def test_rate(self):
        'Create rates'
        cu1 = create_currency('cu1')
        cu2 = create_currency('cu2')

        rate1 = add_currency_rate(cu1, Decimal("1.3"))
        rate2 = add_currency_rate(cu2, Decimal("1"))
        self.assertTrue(rate1)
        self.assertTrue(rate2)

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
    def test_round(self):
        "Test simple round"
        cu = create_currency('cu')
        cu.rounding = Decimal('0.001')
        cu.digits = 3
        cu.save()

        rounded = cu.round(Decimal('1.2345678'))

        self.assertEqual(rounded, Decimal('1.235'))

    @with_transaction()
    def test_round_non_unity(self):
        "Test round with non unity"
        cu = create_currency('cu')
        cu.rounding = Decimal('0.02')
        cu.digits = 2
        cu.save()

        rounded = cu.round(Decimal('1.2345'))

        self.assertEqual(rounded, Decimal('1.24'))

    @with_transaction()
    def test_round_big_number(self):
        "Test rounding big number"
        cu = create_currency('cu')

        rounded = cu.round(Decimal('1E50'))

        self.assertEqual(rounded, Decimal('1E50'))

    @with_transaction()
    def test_round_negative(self):
        "Test rounding with negative rounding"
        cu = create_currency('cu')
        cu.rounding = -Decimal('0.1')
        cu.digits = 1
        cu.save()

        rounded = cu.round(Decimal('1.23'))

        self.assertEqual(rounded, Decimal('1.2'))

    @with_transaction()
    def test_round_zero(self):
        "Test rounding with 0 as rounding"
        cu = create_currency('cu')
        cu.rounding = Decimal('0')
        cu.save()

        rounded = cu.round(Decimal('1.2345'))

        self.assertEqual(rounded, Decimal('1.2345'))

    @with_transaction()
    def test_round_opposite(self):
        "Test the opposite rounding"
        cu = create_currency('cu')
        cu.save()

        rounded = cu.round(Decimal('1.235'))
        self.assertEqual(rounded, Decimal('1.24'))
        opposite_rounded = cu.round(Decimal('1.235'), opposite=True)
        self.assertEqual(opposite_rounded, Decimal('1.24'))

    @with_transaction()
    def test_round_opposite_HALF_DOWN(self):
        "Test the oposite rounding of ROUND_HALF_DOWN"
        cu = create_currency('cu')
        cu.save()

        rounded = cu.round(Decimal('1.235'), rounding=ROUND_HALF_DOWN)
        self.assertEqual(rounded, Decimal('1.23'))
        opposite_rounded = cu.round(
            Decimal('1.235'), rounding=ROUND_HALF_DOWN, opposite=True)
        self.assertEqual(opposite_rounded, Decimal('1.24'))

    @with_transaction()
    def test_is_zero(self):
        "Test is zero"
        cu = create_currency('cu')
        cu.rounding = Decimal('0.001')
        cu.digits = 3
        cu.save()

        for value, result in [
                (Decimal('0'), True),
                (Decimal('0.0002'), True),
                (Decimal('0.0009'), False),
                (Decimal('0.002'), False),
                ]:
            with self.subTest(value=value):
                self.assertEqual(cu.is_zero(value), result)
            with self.subTest(value=-value):
                self.assertEqual(cu.is_zero(-value), result)

    @with_transaction()
    def test_is_zero_negative(self):
        "Test is zero with negative rounding"
        cu = create_currency('cu')
        cu.rounding = Decimal('-0.001')
        cu.digits = 3
        cu.save()

        for value, result in [
                (Decimal('0'), True),
                (Decimal('0.0002'), True),
                (Decimal('0.0009'), False),
                (Decimal('0.002'), False),
                ]:
            with self.subTest(value=value):
                self.assertEqual(cu.is_zero(value), result)
            with self.subTest(value=-value):
                self.assertEqual(cu.is_zero(-value), result)

    @with_transaction()
    def test_is_zero_zero(self):
        "Test is zero with 0 as rounding"
        cu = create_currency('cu')
        cu.rounding = Decimal('0')
        cu.save()

        for value, result in [
                (Decimal('0'), True),
                (Decimal('0.0002'), False),
                (Decimal('0.0009'), False),
                (Decimal('0.002'), False),
                ]:
            with self.subTest(value=value):
                self.assertEqual(cu.is_zero(value), result)
            with self.subTest(value=-value):
                self.assertEqual(cu.is_zero(-value), result)

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
                    'currency', 'in', list(map(int, currencies)),
                    )], 0, None, None)
        self.assertFalse(rates)

    @with_transaction()
    def test_currency_rate_sql(self):
        "Test currency rate SQL"
        pool = Pool()
        Currency = pool.get('currency.currency')
        Rate = pool.get('currency.currency.rate')
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
        if backend.name == 'sqlite':
            query.columns[-1].output_name += (
                ' [%s]' % Rate.date.sql_type().base)
        cursor.execute(*query)
        data = set(cursor)
        result = {
            (cu1.id, Decimal(1), date(2017, 1, 1), date(2017, 2, 1)),
            (cu1.id, Decimal(2), date(2017, 2, 1), date(2017, 3, 1)),
            (cu1.id, Decimal(3), date(2017, 3, 1), None),
            (cu2.id, Decimal(2), date(2017, 2, 1), date(2017, 4, 1)),
            (cu2.id, Decimal(4), date(2017, 4, 1), None),
            }

        self.assertSetEqual(data, result)


class ECBtestCase(unittest.TestCase):

    def test_rate_EUR_week_ago(self):
        "Fetch EUR rates a week ago"
        week_ago = datetime.date.today() - datetime.timedelta(days=7)

        rates = get_rates('EUR', week_ago)

        self.assertNotIn('EUR', rates)
        self.assertIn('USD', rates)

    def test_rate_USD_week_ago(self):
        "Fetch USD rates a week ago"
        week_ago = datetime.date.today() - datetime.timedelta(days=7)

        rates = get_rates('USD', week_ago)

        self.assertIn('EUR', rates)
        self.assertNotIn('USD', rates)

    def test_rate_EUR_on_weekend(self):
        "Fetch EUR rates on weekend"

        rates_fr = get_rates('EUR', datetime.date(2022, 9, 30))
        rates_sa = get_rates('EUR', datetime.date(2022, 10, 2))
        rates_su = get_rates('EUR', datetime.date(2022, 10, 2))

        self.assertEqual(rates_sa, rates_fr)
        self.assertEqual(rates_su, rates_fr)

    def test_rate_USD_on_weekend(self):
        "Fetch USD rates on weekend"

        rates_fr = get_rates('USD', datetime.date(2022, 9, 30))
        rates_sa = get_rates('USD', datetime.date(2022, 10, 2))
        rates_su = get_rates('USD', datetime.date(2022, 10, 2))

        self.assertEqual(rates_sa, rates_fr)
        self.assertEqual(rates_su, rates_fr)

    def test_rate_EUR_start_date(self):
        "Fetch EUR rates at start date"

        rates = get_rates('EUR', datetime.date(1999, 1, 4))

        self.assertEqual(rates['USD'], Decimal('1.1789'))

    def test_rate_USD_start_date(self):
        "Fetch USD rates at start date"

        rates = get_rates('USD', datetime.date(1999, 1, 4))

        self.assertEqual(rates['EUR'], Decimal('0.8482'))

    def test_rate_in_future(self):
        "Fetch rate in future raise an error"
        future = datetime.date.today() + datetime.timedelta(days=2)

        with self.assertRaises(RatesNotAvailableError):
            get_rates('USD', future)

    def test_rate_unsupported_currency(self):
        "Fetch rate for unsupported currency"
        with self.assertRaises(UnsupportedCurrencyError):
            get_rates('XXX', datetime.date(2022, 10, 3))


del ModuleTestCase
