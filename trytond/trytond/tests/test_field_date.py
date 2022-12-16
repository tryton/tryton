# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from sql import Literal, Select
from sql.functions import CurrentDate

from trytond import backend
from trytond.model.exceptions import RequiredValidationError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction

today = datetime.date(2009, 1, 1)
tomorrow = today + datetime.timedelta(1)
yesterday = today - datetime.timedelta(1)
default_date = datetime.date(2000, 1, 1)


class FieldDateTestCase(unittest.TestCase):
    "Test Field Date"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create date"
        Date = Pool().get('test.date')

        date, date_none = Date.create([{
                    'date': today,
                    }, {
                    'date': None
                    }])

        self.assertEqual(date.date, today)
        self.assertEqual(date_none.date, None)

    @with_transaction()
    def test_create_date_string(self):
        "Test create date with date string"
        Date = Pool().get('test.date')

        date, = Date.create([{
                    'date': str(today),
                    }])

        self.assertEqual(date.date, today)

    @with_transaction()
    def test_create_invalid_date_string(self):
        "Test create date with invalid date string"
        Date = Pool().get('test.date')

        with self.assertRaises(ValueError):
            Date.create([{
                        'date': '2009-02-29',
                        }])

    @with_transaction()
    def test_create_without_default(self):
        "Test create date without default"
        Date = Pool().get('test.date')

        date, = Date.create([{}])

        self.assertEqual(date.date, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create date with default"
        Date = Pool().get('test.date_default')

        date, = Date.create([{}])

        self.assertEqual(date.date, default_date)

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create date with SQL value"
        Date = Pool().get('test.date')

        date, = Date.create([{'date': CurrentDate()}])

        self.assertTrue(date.date)

    @with_transaction()
    def test_set_sql_value(self):
        "Test cannot set SQL value"
        Date = Pool().get('test.date')

        date = Date()

        with self.assertRaises(ValueError):
            date.date = CurrentDate()

    @with_transaction()
    def test_create_non_date(self):
        "Test create date with non date"
        Date = Pool().get('test.date')

        with self.assertRaises(ValueError):
            Date.create([{
                        'date': 'non date',
                        }])

    @with_transaction()
    def test_create_integer(self):
        "Test create date with integer"
        Date = Pool().get('test.date')

        with self.assertRaises(TypeError):
            Date.create([{
                        'date': 42,
                        }])

    @with_transaction()
    def test_create_datetime(self):
        "Test create date with datetime"
        Date = Pool().get('test.date')

        with self.assertRaises(ValueError):
            Date.create([{
                        'date': datetime.datetime(2009, 1, 1, 12, 0),
                        }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create date required with value"
        Date = Pool().get('test.date_required')

        date, = Date.create([{
                    'date': today,
                    }])

        self.assertEqual(date.date, today)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create date required without value"
        Date = Pool().get('test.date_required')

        with self.assertRaises(RequiredValidationError):
            Date.create([{}])

    @with_transaction()
    def test_search_equals(self):
        "Test search date equals"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_today = Date.search([
                ('date', '=', today),
                ])
        dates_tomorrow = Date.search([
                ('date', '=', tomorrow),
                ])

        self.assertListEqual(dates_today, [date])
        self.assertListEqual(dates_tomorrow, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search date equals None"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': None,
                    }])

        dates = Date.search([
                ('date', '=', None),
                ])

        self.assertListEqual(dates, [date])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search date non equals"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_today = Date.search([
                ('date', '!=', today),
                ])
        dates_tomorrow = Date.search([
                ('date', '!=', tomorrow),
                ])

        self.assertListEqual(dates_today, [])
        self.assertListEqual(dates_tomorrow, [date])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search date non equals None"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': None,
                    }])

        dates = Date.search([
                ('date', '!=', None),
                ])

        self.assertListEqual(dates, [])

    @with_transaction()
    def test_search_in(self):
        "Test search date in"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_today = Date.search([
                ('date', 'in', [today]),
                ])
        dates_tomorrow = Date.search([
                ('date', 'in', [tomorrow]),
                ])
        dates_empty = Date.search([
                ('date', 'in', []),
                ])

        self.assertListEqual(dates_today, [date])
        self.assertListEqual(dates_tomorrow, [])
        self.assertListEqual(dates_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search date in [None]"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': None,
                    }])

        dates = Date.search([
                ('date', 'in', [None]),
                ])

        self.assertListEqual(dates, [date])

    @with_transaction()
    def test_search_not_in(self):
        "Test search date not in"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_today = Date.search([
                ('date', 'not in', [today]),
                ])
        dates_tomorrow = Date.search([
                ('date', 'not in', [tomorrow]),
                ])
        dates_empty = Date.search([
                ('date', 'not in', []),
                ])

        self.assertListEqual(dates_today, [])
        self.assertListEqual(dates_tomorrow, [date])
        self.assertListEqual(dates_empty, [date])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search date not in [None]"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': None,
                    }])

        dates = Date.search([
                ('date', 'not in', [None]),
                ])

        self.assertListEqual(dates, [])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search date in multiple"
        Date = Pool().get('test.date')
        dates = Date.create([{
                    'date': today,
                    }, {
                    'date': tomorrow,
                    }])

        dates_in = Date.search([
                ('date', 'in', [today, tomorrow]),
                ])

        self.assertListEqual(dates_in, dates)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search date not in multiple"
        Date = Pool().get('test.date')
        Date.create([{
                    'date': today,
                    }, {
                    'date': tomorrow,
                    }])

        dates = Date.search([
                ('date', 'not in', [today, tomorrow]),
                ])

        self.assertListEqual(dates, [])

    @with_transaction()
    def test_search_less(self):
        "Test search date less than"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_tomorrow = Date.search([
                ('date', '<', tomorrow),
                ])
        dates_yesterday = Date.search([
                ('date', '<', yesterday),
                ])
        dates_today = Date.search([
                ('date', '<', today),
                ])

        self.assertListEqual(dates_tomorrow, [date])
        self.assertListEqual(dates_yesterday, [])
        self.assertListEqual(dates_today, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search date less than or equals"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_tomorrow = Date.search([
                ('date', '<=', tomorrow),
                ])
        dates_yesterday = Date.search([
                ('date', '<=', yesterday),
                ])
        dates_today = Date.search([
                ('date', '<=', today),
                ])

        self.assertListEqual(dates_tomorrow, [date])
        self.assertListEqual(dates_yesterday, [])
        self.assertListEqual(dates_today, [date])

    @with_transaction()
    def test_search_greater(self):
        "Test search date greater than"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_tomorrow = Date.search([
                ('date', '>', tomorrow),
                ])
        dates_yesterday = Date.search([
                ('date', '>', yesterday),
                ])
        dates_today = Date.search([
                ('date', '>', today),
                ])

        self.assertListEqual(dates_tomorrow, [])
        self.assertListEqual(dates_yesterday, [date])
        self.assertListEqual(dates_today, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search date greater than or equals"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        dates_tomorrow = Date.search([
                ('date', '>=', tomorrow),
                ])
        dates_yesterday = Date.search([
                ('date', '>=', yesterday),
                ])
        dates_today = Date.search([
                ('date', '>=', today),
                ])

        self.assertListEqual(dates_tomorrow, [])
        self.assertListEqual(dates_yesterday, [date])
        self.assertListEqual(dates_today, [date])

    @with_transaction()
    def test_write(self):
        "Test write date"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        Date.write([date], {
                'date': yesterday,
                })

        self.assertEqual(date.date, yesterday)

    @with_transaction()
    def test_write_non_date(self):
        "Test write date with non date"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        with self.assertRaises(ValueError):
            Date.write([date], {
                    'date': 'non date',
                    })

    @with_transaction()
    def test_write_integer(self):
        "Test write date with integer"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        with self.assertRaises(TypeError):
            Date.write([date], {
                    'date': 42,
                    })

    @with_transaction()
    def test_write_datetime(self):
        "Test write date with datetime"
        Date = Pool().get('test.date')
        date, = Date.create([{
                    'date': today,
                    }])

        with self.assertRaises(ValueError):
            Date.write([date], {
                    'date': datetime.datetime(2009, 1, 1, 12, 0),
                    })

    @unittest.skipIf(backend.name == 'sqlite',
        "SQLite does not support timezone others than utc and localtime")
    @with_transaction()
    def test_sql_cast_timezone(self):
        "Cast datetime to date with timezone"
        Date = Pool().get('test.date')
        expression = Date.date.sql_cast(
            Literal(datetime.datetime(2021, 10, 14, 22, 00)),
            timezone='Europe/Brussels')
        cursor = Transaction().connection.cursor()

        cursor.execute(*Select([expression]))
        result, = cursor.fetchone()

        self.assertEqual(result, datetime.date(2021, 10, 15))
