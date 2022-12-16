# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.tests.test_tryton import install_module, with_transaction
from trytond.pool import Pool


class ModelView(unittest.TestCase):
    "Test ModelView"

    @classmethod
    def setUpClass(cls):
        install_module('tests')

    @with_transaction()
    def test_changed_values(self):
        "Test ModelView._changed_values"
        pool = Pool()
        Model = pool.get('test.modelview.changed_values')
        Target = pool.get('test.modelview.changed_values.target')

        record = Model()

        self.assertEqual(record._changed_values, {})

        record.name = 'foo'
        record.target = Target(1)
        record.ref_target = Target(2)
        record.targets = [Target(name='bar')]
        self.assertEqual(record._changed_values, {
                'name': 'foo',
                'target': 1,
                'ref_target': 'test.modelview.changed_values.target,2',
                'targets': {
                    'add': [
                        (0, {'name': 'bar'}),
                        ],
                    },
                })

        record = Model(name='test', target=1, targets=[
                {'id': 1, 'name': 'foo'},
                {'id': 2},
                ], m2m_targets=[5, 6, 7])

        self.assertEqual(record._changed_values, {})

        target = record.targets[0]
        target.name = 'bar'
        record.targets = [target]
        record.m2m_targets = [Target(9), Target(10)]
        self.assertEqual(record._changed_values, {
                'targets': {
                    'update': [{'id': 1, 'name': 'bar'}],
                    'remove': [2],
                    },
                'm2m_targets': [9, 10],
                })

        # change only one2many record
        record = Model(targets=[{'id': 1, 'name': 'foo'}])
        self.assertEqual(record._changed_values, {})

        target, = record.targets
        target.name = 'bar'
        record.targets = record.targets
        self.assertEqual(record._changed_values, {
                'targets': {
                    'update': [{'id': 1, 'name': 'bar'}],
                    },
                })


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (ModelView,):
        suite.addTests(func(testcase))
    return suite
