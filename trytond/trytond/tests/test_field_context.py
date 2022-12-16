# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldContextTestCase(unittest.TestCase):
    "Test context on field"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_context(self):
        pool = Pool()
        Parent = pool.get('test.field_context.parent')
        Child = pool.get('test.field_context.child')
        child = Child()
        child.save()
        parent = Parent(name='foo', child=child)
        parent.save()
        self.assertEqual(parent.child._context['name'], 'foo')
        self.assertEqual(parent.child._context['rec_name'], '')

        parent.name = 'bar'
        parent.save()
        self.assertEqual(parent.child._context['name'], 'bar')
        self.assertEqual(parent.child._context['rec_name'], '')
