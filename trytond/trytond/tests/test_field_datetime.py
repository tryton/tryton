# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from sql.functions import CurrentTimestamp

from trytond.model.exceptions import (
    RequiredValidationError, TimeFormatValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction

today = datetime.datetime(2009, 1, 1, 12, 0, 0)
tomorrow = today + datetime.timedelta(1)
yesterday = today - datetime.timedelta(1)
default_datetime = datetime.datetime(2000, 1, 1, 12, 0, 0)


class FieldDateTimeTestCase(unittest.TestCase):
    "Test Field DateTime"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create datetime"
        DateTime = Pool().get('test.datetime')

        datetime, datetime_none = DateTime.create([{
                    'datetime': today,
                    }, {
                    'datetime': None
                    }])

        self.assertEqual(datetime.datetime, today)
        self.assertEqual(datetime_none.datetime, None)

    @with_transaction()
    def test_create_datetime_string(self):
        "Test create datetime with datetime string"
        DateTime = Pool().get('test.datetime')

        datetime, = DateTime.create([{
                    'datetime': str(today),
                    }])

        self.assertEqual(datetime.datetime, today)

    @with_transaction()
    def test_create_invalid_datetime_string(self):
        "Test create datetime with invalid datetime string"
        DateTime = Pool().get('test.datetime')

        with self.assertRaises(ValueError):
            DateTime.create([{
                        'datetime': '2009-02-29',
                        }])

    @with_transaction()
    def test_create_without_default(self):
        "Test create datetime without default"
        DateTime = Pool().get('test.datetime')

        datetime, = DateTime.create([{}])

        self.assertEqual(datetime.datetime, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create datetime with default"
        DateTime = Pool().get('test.datetime_default')

        datetime, = DateTime.create([{}])

        self.assertEqual(datetime.datetime, default_datetime)

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create datetime with SQL value"
        DateTime = Pool().get('test.datetime')

        datetime, = DateTime.create([{
                    'datetime': DateTime.datetime.sql_cast(CurrentTimestamp()),
                    }])

        self.assertTrue(datetime.datetime)

    @with_transaction()
    def test_create_non_datetime(self):
        "Test create datetime with non datetime"
        DateTime = Pool().get('test.datetime')

        with self.assertRaises(ValueError):
            DateTime.create([{
                        'datetime': 'non datetime',
                        }])

    @with_transaction()
    def test_create_integer(self):
        "Test create datetime with integer"
        DateTime = Pool().get('test.datetime')

        with self.assertRaises(TypeError):
            DateTime.create([{
                        'datetime': 42,
                        }])

    @with_transaction()
    def test_create_date(self):
        "Test create datetime with date"
        DateTime = Pool().get('test.datetime')

        with self.assertRaises(TypeError):
            DateTime.create([{
                        'datetime': datetime.date(2009, 1, 1),
                        }])

    @with_transaction()
    def test_create_microsecond(self):
        "Test create datetime with microsecond"
        DateTime = Pool().get('test.datetime_required')

        datetime, = DateTime.create([{
                    'datetime': today.replace(microsecond=1),
                    }])

        self.assertEqual(datetime.datetime, today)

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create datetime required with value"
        DateTime = Pool().get('test.datetime_required')

        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        self.assertEqual(datetime.datetime, today)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create datetime required without value"
        DateTime = Pool().get('test.datetime_required')

        with self.assertRaises(RequiredValidationError):
            DateTime.create([{}])

    @with_transaction()
    def test_create_format_valid(self):
        "Test create datetime with valid format"
        DateTime = Pool().get('test.datetime_format')

        datetime_, = DateTime.create([{
                    'datetime': datetime.datetime(2009, 1, 1, 12, 30),
                    }])

        self.assertEqual(
            datetime_.datetime, datetime.datetime(2009, 1, 1, 12, 30))

    @with_transaction()
    def test_create_format_invalid(self):
        "Test create datetime with invalid format"
        DateTime = Pool().get('test.datetime_format')

        with self.assertRaises(TimeFormatValidationError):
            DateTime.create([{
                        'datetime': datetime.datetime(2009, 1, 1, 12, 30, 25),
                        }])

    @with_transaction()
    def test_search_equals(self):
        "Test search datetime equals"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_today = DateTime.search([
                ('datetime', '=', today),
                ])
        datetimes_tomorrow = DateTime.search([
                ('datetime', '=', tomorrow),
                ])

        self.assertListEqual(datetimes_today, [datetime])
        self.assertListEqual(datetimes_tomorrow, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search datetime equals None"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': None,
                    }])

        datetimes = DateTime.search([
                ('datetime', '=', None),
                ])

        self.assertListEqual(datetimes, [datetime])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search datetime non equals"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_today = DateTime.search([
                ('datetime', '!=', today),
                ])
        datetimes_tomorrow = DateTime.search([
                ('datetime', '!=', tomorrow),
                ])

        self.assertListEqual(datetimes_today, [])
        self.assertListEqual(datetimes_tomorrow, [datetime])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search datetime non equals None"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': None,
                    }])

        datetimes = DateTime.search([
                ('datetime', '!=', None),
                ])

        self.assertListEqual(datetimes, [])

    @with_transaction()
    def test_search_in(self):
        "Test search datetime in"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_today = DateTime.search([
                ('datetime', 'in', [today]),
                ])
        datetimes_tomorrow = DateTime.search([
                ('datetime', 'in', [tomorrow]),
                ])
        datetimes_empty = DateTime.search([
                ('datetime', 'in', []),
                ])

        self.assertListEqual(datetimes_today, [datetime])
        self.assertListEqual(datetimes_tomorrow, [])
        self.assertListEqual(datetimes_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search datetime in [None]"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': None,
                    }])

        datetimes = DateTime.search([
                ('datetime', 'in', [None]),
                ])

        self.assertListEqual(datetimes, [datetime])

    @with_transaction()
    def test_search_not_in(self):
        "Test search datetime not in"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_today = DateTime.search([
                ('datetime', 'not in', [today]),
                ])
        datetimes_tomorrow = DateTime.search([
                ('datetime', 'not in', [tomorrow]),
                ])
        datetimes_empty = DateTime.search([
                ('datetime', 'not in', []),
                ])

        self.assertListEqual(datetimes_today, [])
        self.assertListEqual(datetimes_tomorrow, [datetime])
        self.assertListEqual(datetimes_empty, [datetime])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search datetime not in [None]"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': None,
                    }])

        datetimes = DateTime.search([
                ('datetime', 'not in', [None]),
                ])

        self.assertListEqual(datetimes, [])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search datetime in multiple"
        DateTime = Pool().get('test.datetime')
        datetimes = DateTime.create([{
                    'datetime': today,
                    }, {
                    'datetime': tomorrow,
                    }])

        datetimes_in = DateTime.search([
                ('datetime', 'in', [today, tomorrow]),
                ])

        self.assertListEqual(datetimes_in, datetimes)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search datetime not in multiple"
        DateTime = Pool().get('test.datetime')
        DateTime.create([{
                    'datetime': today,
                    }, {
                    'datetime': tomorrow,
                    }])

        datetimes = DateTime.search([
                ('datetime', 'not in', [today, tomorrow]),
                ])

        self.assertListEqual(datetimes, [])

    @with_transaction()
    def test_search_less(self):
        "Test search datetime less than"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_tomorrow = DateTime.search([
                ('datetime', '<', tomorrow),
                ])
        datetimes_yesterday = DateTime.search([
                ('datetime', '<', yesterday),
                ])
        datetimes_today = DateTime.search([
                ('datetime', '<', today),
                ])

        self.assertListEqual(datetimes_tomorrow, [datetime])
        self.assertListEqual(datetimes_yesterday, [])
        self.assertListEqual(datetimes_today, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search datetime less than or equals"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_tomorrow = DateTime.search([
                ('datetime', '<=', tomorrow),
                ])
        datetimes_yesterday = DateTime.search([
                ('datetime', '<=', yesterday),
                ])
        datetimes_today = DateTime.search([
                ('datetime', '<=', today),
                ])

        self.assertListEqual(datetimes_tomorrow, [datetime])
        self.assertListEqual(datetimes_yesterday, [])
        self.assertListEqual(datetimes_today, [datetime])

    @with_transaction()
    def test_search_greater(self):
        "Test search datetime greater than"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_tomorrow = DateTime.search([
                ('datetime', '>', tomorrow),
                ])
        datetimes_yesterday = DateTime.search([
                ('datetime', '>', yesterday),
                ])
        datetimes_today = DateTime.search([
                ('datetime', '>', today),
                ])

        self.assertListEqual(datetimes_tomorrow, [])
        self.assertListEqual(datetimes_yesterday, [datetime])
        self.assertListEqual(datetimes_today, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search datetime greater than or equals"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        datetimes_tomorrow = DateTime.search([
                ('datetime', '>=', tomorrow),
                ])
        datetimes_yesterday = DateTime.search([
                ('datetime', '>=', yesterday),
                ])
        datetimes_today = DateTime.search([
                ('datetime', '>=', today),
                ])

        self.assertListEqual(datetimes_tomorrow, [])
        self.assertListEqual(datetimes_yesterday, [datetime])
        self.assertListEqual(datetimes_today, [datetime])

    @with_transaction()
    def test_write(self):
        "Test write datetime"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        DateTime.write([datetime], {
                'datetime': yesterday,
                })

        self.assertEqual(datetime.datetime, yesterday)

    @with_transaction()
    def test_write_non_datetime(self):
        "Test write datetime with non datetime"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        with self.assertRaises(ValueError):
            DateTime.write([datetime], {
                    'datetime': 'non datetime',
                    })

    @with_transaction()
    def test_write_integer(self):
        "Test write datetime with integer"
        DateTime = Pool().get('test.datetime')
        datetime, = DateTime.create([{
                    'datetime': today,
                    }])

        with self.assertRaises(TypeError):
            DateTime.write([datetime], {
                    'datetime': 42,
                    })

    @with_transaction()
    def test_write_date(self):
        "Test write datetime with date"
        DateTime = Pool().get('test.datetime')
        datetime_, = DateTime.create([{
                    'datetime': today,
                    }])

        with self.assertRaises(TypeError):
            DateTime.write([datetime_], {
                    'datetime': datetime.date(2009, 1, 1),
                    })


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldDateTimeTestCase)
