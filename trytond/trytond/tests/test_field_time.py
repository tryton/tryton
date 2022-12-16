# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from sql.functions import CurrentTimestamp

from trytond.model.exceptions import (
    RequiredValidationError, TimeFormatValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction

pre_evening = datetime.time(16, 30)
evening = datetime.time(18, 45, 3)
night = datetime.time(20, 00)
default_time = datetime.time(16, 30)


class FieldTimeTestCase(unittest.TestCase):
    "Test Field Time"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create time"
        Time = Pool().get('test.time')

        time, timenone = Time.create([{
                    'time': evening,
                    }, {
                    'time': None
                    }])

        self.assertEqual(time.time, evening)
        self.assertEqual(timenone.time, None)

    @with_transaction()
    def test_create_timestring(self):
        "Test create time with time string"
        Time = Pool().get('test.time')

        time, = Time.create([{
                    'time': str(evening),
                    }])

        self.assertEqual(time.time, evening)

    @with_transaction()
    def test_create_invalid_timestring(self):
        "Test create time with invalid time string"
        Time = Pool().get('test.time')

        with self.assertRaises(ValueError):
            Time.create([{
                        'time': '2009-02-29',
                        }])

    @with_transaction()
    def test_create_without_default(self):
        "Test create time without default"
        Time = Pool().get('test.time')

        time, = Time.create([{}])

        self.assertEqual(time.time, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create time with default"
        Time = Pool().get('test.time_default')

        time, = Time.create([{}])

        self.assertEqual(time.time, default_time)

    @with_transaction()
    def test_create_with_sql_value(self):
        "Test create time with SQL value"
        Time = Pool().get('test.time_precision')

        time, = Time.create([{'time': Time.time.sql_cast(CurrentTimestamp())}])

        self.assertTrue(time.time)

    @with_transaction()
    def test_set_sql_value(self):
        "Test cannot set SQL value"
        Time = Pool().get('test.time')

        time = Time()

        with self.assertRaises(ValueError):
            time.time = Time.time.sql_cast(CurrentTimestamp())

    @with_transaction()
    def test_create_non_time(self):
        "Test create time with non time"
        Time = Pool().get('test.time')

        with self.assertRaises(ValueError):
            Time.create([{
                        'time': 'non time',
                        }])

    @with_transaction()
    def test_create_integer(self):
        "Test create time with integer"
        Time = Pool().get('test.time')

        with self.assertRaises(ValueError):
            Time.create([{
                        'time': 42,
                        }])

    @with_transaction()
    def test_create_date(self):
        "Test create time with date"
        Time = Pool().get('test.time')

        with self.assertRaises(TypeError):
            Time.create([{
                        'time': datetime.date(2009, 1, 1),
                        }])

    @with_transaction()
    def test_create_microsecond(self):
        "Test create time with microsecond"
        Time = Pool().get('test.time_required')

        time, = Time.create([{
                    'time': evening.replace(microsecond=1),
                    }])

        self.assertEqual(time.time, evening)

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create time required with value"
        Time = Pool().get('test.time_required')

        time, = Time.create([{
                    'time': evening,
                    }])

        self.assertEqual(time.time, evening)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create time required without value"
        Time = Pool().get('test.time_required')

        with self.assertRaises(RequiredValidationError):
            Time.create([{}])

    @with_transaction()
    def test_create_format_valid(self):
        "Test create time with valid format"
        Time = Pool().get('test.time_format')

        time, = Time.create([{
                    'time': datetime.time(12, 30),
                    }])

        self.assertEqual(
            time.time, datetime.time(12, 30))

    @with_transaction()
    def test_create_format_invalid(self):
        "Test create time with invalid format"
        Time = Pool().get('test.time_format')

        with self.assertRaises(TimeFormatValidationError):
            Time.create([{
                        'time': datetime.time(12, 30, 25),
                        }])

    @with_transaction()
    def test_search_equals(self):
        "Test search time equals"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_evening = Time.search([
                ('time', '=', evening),
                ])
        times_night = Time.search([
                ('time', '=', night),
                ])

        self.assertListEqual(times_evening, [time])
        self.assertListEqual(times_night, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search time equals None"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': None,
                    }])

        times = Time.search([
                ('time', '=', None),
                ])

        self.assertListEqual(times, [time])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search time non equals"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_evening = Time.search([
                ('time', '!=', evening),
                ])
        times_night = Time.search([
                ('time', '!=', night),
                ])

        self.assertListEqual(times_evening, [])
        self.assertListEqual(times_night, [time])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search time non equals None"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': None,
                    }])

        times = Time.search([
                ('time', '!=', None),
                ])

        self.assertListEqual(times, [])

    @with_transaction()
    def test_search_in(self):
        "Test search time in"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_evening = Time.search([
                ('time', 'in', [evening]),
                ])
        times_night = Time.search([
                ('time', 'in', [night]),
                ])
        times_empty = Time.search([
                ('time', 'in', []),
                ])

        self.assertListEqual(times_evening, [time])
        self.assertListEqual(times_night, [])
        self.assertListEqual(times_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search time in [None]"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': None,
                    }])

        times = Time.search([
                ('time', 'in', [None]),
                ])

        self.assertListEqual(times, [time])

    @with_transaction()
    def test_search_not_in(self):
        "Test search time not in"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_evening = Time.search([
                ('time', 'not in', [evening]),
                ])
        times_night = Time.search([
                ('time', 'not in', [night]),
                ])
        times_empty = Time.search([
                ('time', 'not in', []),
                ])

        self.assertListEqual(times_evening, [])
        self.assertListEqual(times_night, [time])
        self.assertListEqual(times_empty, [time])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search time not in [None]"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': None,
                    }])

        times = Time.search([
                ('time', 'not in', [None]),
                ])

        self.assertListEqual(times, [])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search time in multiple"
        Time = Pool().get('test.time')
        times = Time.create([{
                    'time': evening,
                    }, {
                    'time': night,
                    }])

        times_in = Time.search([
                ('time', 'in', [evening, night]),
                ])

        self.assertListEqual(times_in, times)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search time not in multiple"
        Time = Pool().get('test.time')
        Time.create([{
                    'time': evening,
                    }, {
                    'time': night,
                    }])

        times = Time.search([
                ('time', 'not in', [evening, night]),
                ])

        self.assertListEqual(times, [])

    @with_transaction()
    def test_search_less(self):
        "Test search time less than"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_night = Time.search([
                ('time', '<', night),
                ])
        times_pre_evening = Time.search([
                ('time', '<', pre_evening),
                ])
        times_evening = Time.search([
                ('time', '<', evening),
                ])

        self.assertListEqual(times_night, [time])
        self.assertListEqual(times_pre_evening, [])
        self.assertListEqual(times_evening, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search time less than or equals"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_night = Time.search([
                ('time', '<=', night),
                ])
        times_pre_evening = Time.search([
                ('time', '<=', pre_evening),
                ])
        times_evening = Time.search([
                ('time', '<=', evening),
                ])

        self.assertListEqual(times_night, [time])
        self.assertListEqual(times_pre_evening, [])
        self.assertListEqual(times_evening, [time])

    @with_transaction()
    def test_search_greater(self):
        "Test search time greater than"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_night = Time.search([
                ('time', '>', night),
                ])
        times_pre_evening = Time.search([
                ('time', '>', pre_evening),
                ])
        times_evening = Time.search([
                ('time', '>', evening),
                ])

        self.assertListEqual(times_night, [])
        self.assertListEqual(times_pre_evening, [time])
        self.assertListEqual(times_evening, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search time greater than or equals"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        times_night = Time.search([
                ('time', '>=', night),
                ])
        times_pre_evening = Time.search([
                ('time', '>=', pre_evening),
                ])
        times_evening = Time.search([
                ('time', '>=', evening),
                ])

        self.assertListEqual(times_night, [])
        self.assertListEqual(times_pre_evening, [time])
        self.assertListEqual(times_evening, [time])

    @with_transaction()
    def test_write(self):
        "Test write time"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        Time.write([time], {
                'time': pre_evening,
                })

        self.assertEqual(time.time, pre_evening)

    @with_transaction()
    def test_write_non_time(self):
        "Test write time with non time"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        with self.assertRaises(ValueError):
            Time.write([time], {
                    'time': 'non time',
                    })

    @with_transaction()
    def test_write_integer(self):
        "Test write time with integer"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        with self.assertRaises(ValueError):
            Time.write([time], {
                    'time': 42,
                    })

    @with_transaction()
    def test_write_date(self):
        "Test write time with date"
        Time = Pool().get('test.time')
        time, = Time.create([{
                    'time': evening,
                    }])

        with self.assertRaises(TypeError):
            Time.write([time], {
                    'time': datetime.date(2009, 1, 1),
                    })
