# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from trytond.exceptions import UserError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction

minute = datetime.timedelta(minutes=1)
hour = datetime.timedelta(hours=1)
day = datetime.timedelta(days=1)
default_timedelta = datetime.timedelta(seconds=3600)


class FieldTimeDeltaTestCase(unittest.TestCase):
    "Test Field TimeDelta"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create timedelta"
        TimeDelta = Pool().get('test.timedelta')

        timedelta, timedelta_none = TimeDelta.create([{
                    'timedelta': hour,
                    }, {
                    'timedelta': None
                    }])

        self.assertEqual(timedelta.timedelta, hour)
        self.assertEqual(timedelta_none.timedelta, None)

    @with_transaction()
    def test_create_without_default(self):
        "Test create timedelta without default"
        TimeDelta = Pool().get('test.timedelta')

        timedelta, = TimeDelta.create([{}])

        self.assertEqual(timedelta.timedelta, None)

    @with_transaction()
    def test_create_with_default(self):
        "Test create timedelta with default"
        TimeDelta = Pool().get('test.timedelta_default')

        timedelta, = TimeDelta.create([{}])

        self.assertEqual(timedelta.timedelta, default_timedelta)

    @with_transaction()
    def test_create_non_timedelta(self):
        "Test create timedelta with non timedelta"
        TimeDelta = Pool().get('test.timedelta')

        with self.assertRaises(ValueError):
            TimeDelta.create([{
                        'timedelta': 'non timedelta',
                        }])

    @with_transaction()
    def test_create_integer(self):
        "Test create timedelta with integer"
        TimeDelta = Pool().get('test.timedelta')

        with self.assertRaises(ValueError):
            TimeDelta.create([{
                        'timedelta': 42,
                        }])

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create timedelta required with value"
        TimeDelta = Pool().get('test.timedelta_required')

        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        self.assertEqual(timedelta.timedelta, hour)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create timedelta required without value"
        TimeDelta = Pool().get('test.timedelta_required')

        with self.assertRaises(UserError):
            TimeDelta.create([{}])

    @with_transaction()
    def test_search_equals(self):
        "Test search timedelta equals"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_hour = TimeDelta.search([
                ('timedelta', '=', hour),
                ])
        timedeltas_day = TimeDelta.search([
                ('timedelta', '=', day),
                ])

        self.assertListEqual(timedeltas_hour, [timedelta])
        self.assertListEqual(timedeltas_day, [])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search timedelta equals None"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': None,
                    }])

        timedeltas = TimeDelta.search([
                ('timedelta', '=', None),
                ])

        self.assertListEqual(timedeltas, [timedelta])

    @with_transaction()
    def test_search_non_equals(self):
        "Test search timedelta non equals"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_hour = TimeDelta.search([
                ('timedelta', '!=', hour),
                ])
        timedeltas_day = TimeDelta.search([
                ('timedelta', '!=', day),
                ])

        self.assertListEqual(timedeltas_hour, [])
        self.assertListEqual(timedeltas_day, [timedelta])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search timedelta non equals None"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': None,
                    }])

        timedeltas = TimeDelta.search([
                ('timedelta', '!=', None),
                ])

        self.assertListEqual(timedeltas, [])

    @with_transaction()
    def test_search_in(self):
        "Test search timedelta in"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_hour = TimeDelta.search([
                ('timedelta', 'in', [hour]),
                ])
        timedeltas_day = TimeDelta.search([
                ('timedelta', 'in', [day]),
                ])
        timedeltas_empty = TimeDelta.search([
                ('timedelta', 'in', []),
                ])

        self.assertListEqual(timedeltas_hour, [timedelta])
        self.assertListEqual(timedeltas_day, [])
        self.assertListEqual(timedeltas_empty, [])

    @with_transaction()
    def test_search_in_none(self):
        "Test search timedelta in [None]"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': None,
                    }])

        timedeltas = TimeDelta.search([
                ('timedelta', 'in', [None]),
                ])

        self.assertListEqual(timedeltas, [timedelta])

    @with_transaction()
    def test_search_not_in(self):
        "Test search timedelta not in"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_hour = TimeDelta.search([
                ('timedelta', 'not in', [hour]),
                ])
        timedeltas_day = TimeDelta.search([
                ('timedelta', 'not in', [day]),
                ])
        timedeltas_empty = TimeDelta.search([
                ('timedelta', 'not in', []),
                ])

        self.assertListEqual(timedeltas_hour, [])
        self.assertListEqual(timedeltas_day, [timedelta])
        self.assertListEqual(timedeltas_empty, [timedelta])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search timedelta not in [None]"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': None,
                    }])

        timedeltas = TimeDelta.search([
                ('timedelta', 'not in', [None]),
                ])

        self.assertListEqual(timedeltas, [])

    @with_transaction()
    def test_search_in_multi(self):
        "Test search timedelta in multiple"
        TimeDelta = Pool().get('test.timedelta')
        timedeltas = TimeDelta.create([{
                    'timedelta': hour,
                    }, {
                    'timedelta': day,
                    }])

        timedeltas_in = TimeDelta.search([
                ('timedelta', 'in', [hour, day]),
                ])

        self.assertListEqual(timedeltas_in, timedeltas)

    @with_transaction()
    def test_search_not_in_multi(self):
        "Test search timedelta not in multiple"
        TimeDelta = Pool().get('test.timedelta')
        TimeDelta.create([{
                    'timedelta': hour,
                    }, {
                    'timedelta': day,
                    }])

        timedeltas = TimeDelta.search([
                ('timedelta', 'not in', [hour, day]),
                ])

        self.assertListEqual(timedeltas, [])

    @with_transaction()
    def test_search_less(self):
        "Test search timedelta less than"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_day = TimeDelta.search([
                ('timedelta', '<', day),
                ])
        timedeltas_minute = TimeDelta.search([
                ('timedelta', '<', minute),
                ])
        timedeltas_hour = TimeDelta.search([
                ('timedelta', '<', hour),
                ])

        self.assertListEqual(timedeltas_day, [timedelta])
        self.assertListEqual(timedeltas_minute, [])
        self.assertListEqual(timedeltas_hour, [])

    @with_transaction()
    def test_search_less_equals(self):
        "Test search timedelta less than or equals"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_day = TimeDelta.search([
                ('timedelta', '<=', day),
                ])
        timedeltas_minute = TimeDelta.search([
                ('timedelta', '<=', minute),
                ])
        timedeltas_hour = TimeDelta.search([
                ('timedelta', '<=', hour),
                ])

        self.assertListEqual(timedeltas_day, [timedelta])
        self.assertListEqual(timedeltas_minute, [])
        self.assertListEqual(timedeltas_hour, [timedelta])

    @with_transaction()
    def test_search_greater(self):
        "Test search timedelta greater than"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_day = TimeDelta.search([
                ('timedelta', '>', day),
                ])
        timedeltas_minute = TimeDelta.search([
                ('timedelta', '>', minute),
                ])
        timedeltas_hour = TimeDelta.search([
                ('timedelta', '>', hour),
                ])

        self.assertListEqual(timedeltas_day, [])
        self.assertListEqual(timedeltas_minute, [timedelta])
        self.assertListEqual(timedeltas_hour, [])

    @with_transaction()
    def test_search_greater_equals(self):
        "Test search timedelta greater than or equals"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        timedeltas_day = TimeDelta.search([
                ('timedelta', '>=', day),
                ])
        timedeltas_minute = TimeDelta.search([
                ('timedelta', '>=', minute),
                ])
        timedeltas_hour = TimeDelta.search([
                ('timedelta', '>=', hour),
                ])

        self.assertListEqual(timedeltas_day, [])
        self.assertListEqual(timedeltas_minute, [timedelta])
        self.assertListEqual(timedeltas_hour, [timedelta])

    @with_transaction()
    def test_write(self):
        "Test write timedelta"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        TimeDelta.write([timedelta], {
                'timedelta': minute,
                })

        self.assertEqual(timedelta.timedelta, minute)

    @with_transaction()
    def test_write_non_timedelta(self):
        "Test write timedelta with non timedelta"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        with self.assertRaises(ValueError):
            TimeDelta.write([timedelta], {
                    'timedelta': 'non timedelta',
                    })

    @with_transaction()
    def test_write_integer(self):
        "Test write timedelta with integer"
        TimeDelta = Pool().get('test.timedelta')
        timedelta, = TimeDelta.create([{
                    'timedelta': hour,
                    }])

        with self.assertRaises(ValueError):
            TimeDelta.write([timedelta], {
                    'timedelta': 42,
                    })


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(FieldTimeDeltaTestCase)
