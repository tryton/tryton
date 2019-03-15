# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class ModelTestCase(unittest.TestCase):
    'Test Model'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_repr(self):
        'Test repr'
        pool = Pool()
        Model = pool.get('test.model')

        record = Model(name='foo')
        self.assertEqual(
            repr(record), "Pool().get('test.model')(**{'name': 'foo'})")

        record.save()
        self.assertEqual(
            repr(record), "Pool().get('test.model')(%s)" % record.id)

    @with_transaction()
    def test_init_parent(self):
        "Test __init__ with _parent_"
        pool = Pool()
        Model = pool.get('test.model_child')

        values = {
            '_parent_parent.name': "Test",
            }
        record = Model(**values)

        self.assertEqual(record.parent.name, "Test")

    @with_transaction()
    def test_init_parent_parent(self):
        "Test __init__ with _parent_._parent_"
        pool = Pool()
        Model = pool.get('test.model_child_child')

        values = {
            '_parent_parent.name': "Test 1",
            '_parent_parent._parent_parent.name': "Test 2",
            }
        record = Model(**values)

        self.assertEqual(record.parent.name, "Test 1")
        self.assertEqual(record.parent.parent.name, "Test 2")

    @with_transaction()
    def test_names_model(self):
        "Test __names__ for model only"
        pool = Pool()
        Model = pool.get('test.model')

        names = Model.__names__()

        self.assertEqual(names, {'model': "Model"})

    @with_transaction()
    def test_names_field(self):
        "Test __names__ with field"
        pool = Pool()
        Model = pool.get('test.model')

        names = Model.__names__('name')

        self.assertEqual(names, {'model': "Model", 'field': "Name"})


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelTestCase)
