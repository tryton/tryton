# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool


class MultiValueTestCase(unittest.TestCase):
    "Test MultiValue"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_get_multivalue(self):
        "Test get_multivalue"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        value, = ModelValue.search([])
        value.condition = "foo"
        value.value = "bar"
        value.save()

        self.assertEqual(
            record.get_multivalue('value', condition="foo"),
            "bar")

    @with_transaction()
    def test_get_multivalue_extra_pattern(self):
        "Test get_multivalue with extra pattern"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        value, = ModelValue.search([])
        value.value = "bar"
        value.save()

        self.assertEqual(
            record.get_multivalue('value', extra="foo"),
            "bar")

    @with_transaction()
    def test_get_multivalue_default(self):
        "Test get_multivalue default value"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')

        record = ModelMultiValue()
        record.save()

        self.assertEqual(record.get_multivalue('value'), "default")

    @with_transaction()
    def test_get_multivalue_match_none(self):
        "Test get_multivalue does not match None"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        value = ModelValue(record=record, condition="foo", value="bar")
        value.save()

        self.assertEqual(
            record.get_multivalue('value', condition="test"),
            "default")

    @with_transaction()
    def test_set_multivalue(self):
        "Test set_multivalue"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        record.set_multivalue('value', "set", condition="test")

        value, = ModelValue.search([('condition', '=', "test")])
        self.assertEqual(value.record, record)
        self.assertEqual(value.value, "set")

    @with_transaction()
    def test_set_multivalue_extra_pattern(self):
        "Test set_multivalue extra pattern"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        record.set_multivalue('value', "set", extra="foo")

        value, = ModelValue.search([])
        self.assertEqual(value.record, record)
        self.assertEqual(value.value, "set")
        self.assertEqual(value.condition, None)

    @with_transaction()
    def test_set_multivalue_match_none(self):
        "Test set_multivalue matches None"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        record.set_multivalue('value', "set", condition="test")

        self.assertEqual(len(ModelValue.search([])), 2)

    @with_transaction()
    def test_mutlivalue_setter(self):
        "Test multivalue setter"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')

        record, = ModelMultiValue.create([{
                    'value': "setter",
                    }])

        self.assertEqual(record.get_multivalue('value'), "setter")

    @with_transaction()
    def test_mutlivalue_getter(self):
        "Test multivalue getter"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')

        record = ModelMultiValue(value="getter")
        record.save()

        read, = ModelMultiValue.read([record.id], ['value'])
        self.assertEqual(read['value'], "getter")


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MultiValueTestCase)
