#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
import sys
import time
from xmlrpclib import MAXINT
try:
    from itertools import combinations
except ImportError:
    def combinations(iterable, r):
        pool = tuple(iterable)
        n = len(pool)
        if r > n:
            return
        indices = range(r)
        yield tuple(pool[i] for i in indices)
        while True:
            for i in reversed(range(r)):
                if indices[i] != i + n - r:
                    break
            else:
                return
            indices[i] += 1
            for j in range(i+1, r):
                indices[j] = indices[j-1] + 1
            yield tuple(pool[i] for i in indices)
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.test.trigger import TRIGGER_LOGS
from trytond.transaction import Transaction


class TriggerTestCase(unittest.TestCase):
    '''
    Test Trigger
    '''

    def setUp(self):
        install_module('test')
        self.triggered = POOL.get('test.triggered')
        self.trigger = POOL.get('ir.trigger')
        self.trigger_log = POOL.get('ir.trigger.log')
        self.model = POOL.get('ir.model')

    def test0010constraints(self):
        '''
        Test constraints
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id = self.model.search([
                ('model', '=', 'test.triggered'),
                ])[0]

            values = {
                'name': 'Test',
                'model': model_id,
                'on_time': True,
                'condition': 'True',
                'action_model': model_id,
                'action_function': 'test',
            }
            self.assert_(self.trigger.create(values))

            # on_exclusive
            for i in range(1, 4):
                for combination in combinations(['create', 'write', 'delete'], i):
                    combination_values = values.copy()
                    for mode in combination:
                        combination_values['on_%s' % mode] = True
                    self.failUnlessRaises(Exception, self.trigger.create,
                            combination_values)

            # check_condition
            condition_values = values.copy()
            condition_values['condition'] = '='
            self.failUnlessRaises(Exception, self.trigger.create,
                    condition_values)

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger.get_triggers.reset()
            transaction.cursor.rollback()

    def test0020on_create(self):
        '''
        Test on_create
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id = self.model.search([
                ('model', '=', 'test.triggered'),
                ])[0]

            trigger_id = self.trigger.create({
                'name': 'Test',
                'model': model_id,
                'on_create': True,
                'condition': 'True',
                'action_model': model_id,
                'action_function': 'trigger',
                })

            triggered_id = self.triggered.create({
                'name': 'Test',
                })

            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # Trigger with condition
            self.trigger.write(trigger_id, {
                'condition': 'self.name == "Bar"',
                })

            # Matching condition
            triggered_id = self.triggered.create({
                'name': 'Bar',
                })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # Non matching condition
            triggered_id = self.triggered.create({
                'name': 'Foo',
                })
            self.assert_(TRIGGER_LOGS == [])

            # With limit number
            self.trigger.write(trigger_id, {
                'condition': 'True',
                'limit_number': 1,
                })
            triggered_id = self.triggered.create({
                'name': 'Test',
                })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # With minimum delay
            self.trigger.write(trigger_id, {
                'limit_number': 0,
                'minimum_delay': 1,
                })
            triggered_id = self.triggered.create({
                'name': 'Test',
                })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger.get_triggers.reset()
            transaction.cursor.rollback()

    def test0030on_write(self):
        '''
        Test on_write
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id = self.model.search([
                ('model', '=', 'test.triggered'),
                ])[0]

            trigger_id = self.trigger.create({
                'name': 'Test',
                'model': model_id,
                'on_write': True,
                'condition': 'True',
                'action_model': model_id,
                'action_function': 'trigger',
                })

            triggered_id = self.triggered.create({
                'name': 'Test',
                })

            self.triggered.write(triggered_id, {
                'name': 'Foo',
                })
            self.assert_(TRIGGER_LOGS == [])

            # Trigger with condition
            self.trigger.write(trigger_id, {
                'condition': 'self.name == "Bar"',
                })

            # Matching condition
            self.triggered.write(triggered_id, {
                'name': 'Bar',
                })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # No change in condition
            self.triggered.write(triggered_id, {
                'name': 'Bar',
                })
            self.assert_(TRIGGER_LOGS == [])

            # Different change in condition
            self.triggered.write(triggered_id, {
                'name': 'Foo',
                })
            self.assert_(TRIGGER_LOGS == [])

            # With limit number
            self.trigger.write(trigger_id, {
                'condition': 'self.name == "Bar"',
                'limit_number': 1,
                })
            triggered_id = self.triggered.create({
                'name': 'Foo',
                })
            self.triggered.write(triggered_id, {
                'name': 'Bar',
                })
            self.triggered.write(triggered_id, {
                'name': 'Foo',
                })
            self.triggered.write(triggered_id, {
                'name': 'Bar',
                })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # With minimum delay
            self.trigger.write(trigger_id, {
                'limit_number': 0,
                'minimum_delay': MAXINT,
                })
            triggered_id = self.triggered.create({
                'name': 'Foo',
                })
            for name in ('Bar', 'Foo', 'Bar'):
                self.triggered.write(triggered_id, {
                    'name': name,
                    })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            self.trigger.write(trigger_id, {
                'minimum_delay': 0.02,
                })
            triggered_id = self.triggered.create({
                'name': 'Foo',
                })
            for name in ('Bar', 'Foo'):
                self.triggered.write(triggered_id, {
                    'name': name,
                    })
            time.sleep(1.2)
            self.triggered.write(triggered_id, {
                'name': 'Bar',
                })
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id),
                ([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            TRIGGER_LOGS.pop()

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger.get_triggers.reset()
            transaction.cursor.rollback()

    def test0040on_delete(self):
        '''
        Test on_delete
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id = self.model.search([
                ('model', '=', 'test.triggered'),
                ])[0]

            triggered_id = self.triggered.create({
                'name': 'Test',
                })

            trigger_id = self.trigger.create({
                'name': 'Test',
                'model': model_id,
                'on_delete': True,
                'condition': 'True',
                'action_model': model_id,
                'action_function': 'trigger',
                })

            self.triggered.delete(triggered_id)
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Trigger with condition
            self.trigger.write(trigger_id, {
                'condition': 'self.name == "Bar"',
                })

            triggered_id = self.triggered.create({
                'name': 'Bar',
                })

            # Matching condition
            self.triggered.delete(triggered_id)
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            triggered_id = self.triggered.create({
                'name': 'Foo',
                })

            # Non matching condition
            self.triggered.delete(triggered_id)
            self.assert_(TRIGGER_LOGS == [])
            Transaction().delete = {}

            triggered_id = self.triggered.create({
                'name': 'Test',
                })

            # With limit number
            self.trigger.write(trigger_id, {
                'condition': 'True',
                'limit_number': 1,
                })
            self.triggered.delete(triggered_id)
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}
            # Delete trigger logs because SQLite reuse the same triggered_id
            self.trigger_log.delete( self.trigger_log.search([
                ('trigger', '=', trigger_id),
                ]))

            triggered_id = self.triggered.create({
                'name': 'Test',
                })

            # With minimum delay
            self.trigger.write(trigger_id, {
                'limit_number': 0,
                'minimum_delay': 1,
                })
            self.triggered.delete(triggered_id)
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger.get_triggers.reset()
            transaction.cursor.rollback()

    def test0050on_time(self):
        '''
        Test on_time
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id = self.model.search([
                ('model', '=', 'test.triggered'),
                ])[0]

            trigger_id = self.trigger.create({
                'name': 'Test',
                'model': model_id,
                'on_time': True,
                'condition': 'True',
                'action_model': model_id,
                'action_function': 'trigger',
                })

            triggered_id = self.triggered.create({
                'name': 'Test',
                })
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # Trigger with condition
            self.trigger.write(trigger_id, {
                'condition': 'self.name == "Bar"',
                })

            # Matching condition
            self.triggered.write(triggered_id, {
                'name': 'Bar',
                })
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # Non matching condition
            self.triggered.write(triggered_id, {
                'name': 'Foo',
                })
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [])

            # With limit number
            self.trigger.write(trigger_id, {
                'condition': 'True',
                'limit_number': 1,
                })
            self.trigger.trigger_time()
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()

            # Delete trigger logs of limit number test
            self.trigger_log.delete( self.trigger_log.search([
                ('trigger', '=', trigger_id),
                ]))

            # With minimum delay
            self.trigger.write(trigger_id, {
                'limit_number': 0,
                'minimum_delay': MAXINT,
                })
            self.trigger.trigger_time()
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Delete trigger logs of previous minimum delay test
            self.trigger_log.delete(self.trigger_log.search([
                ('trigger', '=', trigger_id),
                ]))

            self.trigger.write(trigger_id, {
                'minimum_delay': 0.02,
                })
            self.trigger.trigger_time()
            time.sleep(1.2)
            self.trigger.trigger_time()
            self.assert_(TRIGGER_LOGS == [([triggered_id], trigger_id),
                ([triggered_id], trigger_id)])
            TRIGGER_LOGS.pop()
            TRIGGER_LOGS.pop()
            Transaction().delete = {}

            # Restart the cache on the get_triggers method of ir.trigger
            self.trigger.get_triggers.reset()
            transaction.cursor.rollback()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TriggerTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
