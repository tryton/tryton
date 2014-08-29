# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class FieldContextTestCase(unittest.TestCase):
    "Test context on field"

    def setUp(self):
        install_module('tests')

    def test_context(self):
        Parent = POOL.get('test.field_context.parent')
        Child = POOL.get('test.field_context.child')
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            child = Child()
            child.save()
            parent = Parent(name='foo', child=child)
            parent.save()
            self.assertEqual(parent.child._context['name'], 'foo')

            parent.name = 'bar'
            parent.save()
            self.assertEqual(parent.child._context['name'], 'bar')


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (FieldContextTestCase,):
        suite.addTests(func(testcase))
    return suite
