# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import time
import datetime
from itertools import combinations

from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.tests.trigger import TRIGGER_LOGS
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.pyson import PYSONEncoder, Eval


class TriggerTestCase(unittest.TestCase):
    'Test Trigger'

    def setUp(self):
        install_module('tests')
        self.triggered = POOL.get('test.triggered')
        self.trigger = POOL.get('ir.trigger')
        self.trigger_log = POOL.get('ir.trigger.log')
        self.model = POOL.get('ir.model')

    def test0010constraints(self):
        'Test constraints'
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            model, = self.model.search([
                    ('model', '=', 'test.triggered'),
                    ])
            action_model, = self.model.search([
                    ('model', '=', 'test.trigger_action'),
                    ])

            values = {
                'name': 'Test',
                'model': model.id,
                'on_time': True,
                'condition': 'true',
                'action_model': action_model.id,
                'action_function': 'test',
                }
            self.assert_(self.trigger.create([values]))

        # on_exclusive
        for i in range(1, 4):
            for combination in combinations(
                    ['create', 'write', 'delete'], i):
                with Transaction().start(DB_NAME, USER, context=CONTEXT):
                    combination_values = values.copy()
                    for mode in combination:
                        combination_values['on_%s' % mode] = True
                    self.assertRaises(UserError, self.trigger.create,
                        [combination_values])

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            # check_condition
            condition_values = values.copy()
            condition_values['condition'] = '='
            self.assertRaises(UserError, self.trigger.create,
                [condition_values])

        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger._get_triggers_cache.clear()

    def test0020on_create(self):
        'Test on_create'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([
                    ('model', '=', 'test.triggered'),
                    ])
            action_model, = self.model.search([
                    ('model', '=', 'test.trigger_action'),
                    ])

            trigger, = self.trigger.create([{
                        'name': 'Test',
                        'model': model.id,
                        'on_create': True,
                        'condition': 'true',
                        'action_model': action_model.id,
                        'action_function': 'trigger',
                        }])

            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])

            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # Trigger with condition
            condition = PYSONEncoder().encode(
                Eval('self', {}).get('name') == 'Bar')
            self.trigger.write([trigger], {
                    'condition': condition,
                    })

            # Matching condition
            triggered, = self.triggered.create([{
                        'name': 'Bar',
                        }])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # Non matching condition
            triggered, = self.triggered.create([{
                        'name': 'Foo',
                        }])
            self.assertEqual(TRIGGER_LOGS, [])

            # With limit number
            self.trigger.write([trigger], {
                    'condition': 'true',
                    'limit_number': 1,
                    })
            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # With minimum delay
            self.trigger.write([trigger], {
                    'limit_number': 0,
                    'minimum_time_delay': datetime.timedelta(hours=1),
                    })
            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger._get_triggers_cache.clear()
            transaction.cursor.rollback()

    def test0030on_write(self):
        'Test on_write'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([
                    ('model', '=', 'test.triggered'),
                    ])
            action_model, = self.model.search([
                    ('model', '=', 'test.trigger_action'),
                    ])

            trigger, = self.trigger.create([{
                        'name': 'Test',
                        'model': model.id,
                        'on_write': True,
                        'condition': 'true',
                        'action_model': action_model.id,
                        'action_function': 'trigger',
                        }])

            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])

            self.triggered.write([triggered], {
                    'name': 'Foo',
                    })
            self.assertEqual(TRIGGER_LOGS, [])

            # Trigger with condition
            condition = PYSONEncoder().encode(
                Eval('self', {}).get('name') == 'Bar')
            self.trigger.write([trigger], {
                    'condition': condition,
                    })

            # Matching condition
            self.triggered.write([triggered], {
                    'name': 'Bar',
                    })
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # No change in condition
            self.triggered.write([triggered], {
                    'name': 'Bar',
                    })
            self.assertEqual(TRIGGER_LOGS, [])

            # Different change in condition
            self.triggered.write([triggered], {
                    'name': 'Foo',
                    })
            self.assertEqual(TRIGGER_LOGS, [])

            # With limit number
            condition = PYSONEncoder().encode(
                Eval('self', {}).get('name') == 'Bar')
            self.trigger.write([trigger], {
                    'condition': condition,
                    'limit_number': 1,
                    })
            triggered, = self.triggered.create([{
                        'name': 'Foo',
                        }])
            self.triggered.write([triggered], {
                    'name': 'Bar',
                    })
            self.triggered.write([triggered], {
                    'name': 'Foo',
                    })
            self.triggered.write([triggered], {
                    'name': 'Bar',
                    })
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # With minimum delay
            self.trigger.write([trigger], {
                    'limit_number': 0,
                    'minimum_time_delay': datetime.timedelta.max,
                    })
            triggered, = self.triggered.create([{
                        'name': 'Foo',
                        }])
            for name in ('Bar', 'Foo', 'Bar'):
                self.triggered.write([triggered], {
                        'name': name,
                        })
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            self.trigger.write([trigger], {
                    'minimum_time_delay': datetime.timedelta(seconds=1),
                    })
            triggered, = self.triggered.create([{
                        'name': 'Foo',
                        }])
            for name in ('Bar', 'Foo'):
                self.triggered.write([triggered], {
                        'name': name,
                        })
            time.sleep(1.2)
            self.triggered.write([triggered], {
                    'name': 'Bar',
                    })
            self.assertEqual(TRIGGER_LOGS,
                [([triggered], trigger), ([triggered], trigger)])
            TRIGGER_LOGS.pop()
            TRIGGER_LOGS.pop()

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger._get_triggers_cache.clear()
            transaction.cursor.rollback()

    def test0040on_delete(self):
        'Test on_delete'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([
                    ('model', '=', 'test.triggered'),
                    ])
            action_model, = self.model.search([
                    ('model', '=', 'test.trigger_action'),
                    ])

            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])

            trigger, = self.trigger.create([{
                        'name': 'Test',
                        'model': model.id,
                        'on_delete': True,
                        'condition': 'true',
                        'action_model': action_model.id,
                        'action_function': 'trigger',
                        }])

            self.triggered.delete([triggered])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Trigger with condition
            condition = PYSONEncoder().encode(
                Eval('self', {}).get('name') == 'Bar')
            self.trigger.write([trigger], {
                    'condition': condition,
                    })

            triggered, = self.triggered.create([{
                        'name': 'Bar',
                        }])

            # Matching condition
            self.triggered.delete([triggered])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            triggered, = self.triggered.create([{
                        'name': 'Foo',
                        }])

            # Non matching condition
            self.triggered.delete([triggered])
            self.assertEqual(TRIGGER_LOGS, [])
            Transaction().delete = {}

            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])

            # With limit number
            self.trigger.write([trigger], {
                    'condition': 'true',
                    'limit_number': 1,
                    })
            self.triggered.delete([triggered])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}
            # Delete trigger logs because SQLite reuse the same triggered_id
            self.trigger_log.delete(self.trigger_log.search([
                        ('trigger', '=', trigger.id),
                        ]))

            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])

            # With minimum delay
            self.trigger.write([trigger], {
                    'limit_number': 0,
                    'minimum_time_delay': datetime.timedelta(hours=1),
                    })
            self.triggered.delete([triggered])
            self.assertEqual(TRIGGER_LOGS, [([triggered], trigger)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger._get_triggers_cache.clear()
            transaction.cursor.rollback()

    def test0050on_time(self):
        'Test on_time'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([
                    ('model', '=', 'test.triggered'),
                    ])
            action_model, = self.model.search([
                    ('model', '=', 'test.trigger_action'),
                    ])

            trigger, = self.trigger.create([{
                        'name': 'Test',
                        'model': model.id,
                        'on_time': True,
                        'condition': 'true',
                        'action_model': action_model.id,
                        'action_function': 'trigger',
                        }])

            triggered, = self.triggered.create([{
                        'name': 'Test',
                        }])
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # Trigger with condition
            condition = PYSONEncoder().encode(
                Eval('self', {}).get('name') == 'Bar')
            self.trigger.write([trigger], {
                    'condition': condition,
                    })

            # Matching condition
            self.triggered.write([triggered], {
                    'name': 'Bar',
                    })
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # Non matching condition
            self.triggered.write([triggered], {
                    'name': 'Foo',
                    })
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [])

            # With limit number
            self.trigger.write([trigger], {
                    'condition': 'true',
                    'limit_number': 1,
                    })
            self.trigger.trigger_time()
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered], trigger)])
            TRIGGER_LOGS.pop()

            # Delete trigger logs of limit number test
            self.trigger_log.delete(self.trigger_log.search([
                        ('trigger', '=', trigger.id),
                        ]))

            # With minimum delay
            self.trigger.write([trigger], {
                    'limit_number': 0,
                    'minimum_time_delay': datetime.timedelta.max,
                    })
            self.trigger.trigger_time()
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered], trigger)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Delete trigger logs of previous minimum delay test
            self.trigger_log.delete(self.trigger_log.search([
                        ('trigger', '=', trigger.id),
                        ]))

            self.trigger.write([trigger], {
                    'minimum_time_delay': datetime.timedelta(seconds=1),
                    })
            self.trigger.trigger_time()
            time.sleep(1.2)
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered], trigger),
                    ([triggered], trigger)])
            TRIGGER_LOGS.pop()
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger._get_triggers_cache.clear()
            transaction.cursor.rollback()


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TriggerTestCase)
