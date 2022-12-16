# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


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
    def test_get_multivalue_many2one(self):
        "Test get_multivalue for Many2One"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        Target = pool.get('test.model_multivalue.target')

        target = Target(name="Target")
        target.save()
        record = ModelMultiValue(value_many2one=target)
        record.save()

        self.assertEqual(record.get_multivalue('value_many2one'), target)

    @with_transaction()
    def test_get_multivalue_multiselection(self):
        "Test get_multivalue for MultiSelection"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')

        record = ModelMultiValue(value_multiselection=("foo", "bar"))
        record.save()

        self.assertEqual(
            record.get_multivalue('value_multiselection'), ("bar", "foo"))

    @with_transaction()
    def test_get_multivalue_reference(self):
        "Test get_multivalue for Reference"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        Target = pool.get('test.model_multivalue.target')

        target = Target(name="Target")
        target.save()
        record = ModelMultiValue(value_reference=target)
        record.save()

        self.assertEqual(record.get_multivalue('value_reference'), target)

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
    def test_set_multivalue_other_default(self):
        "Test set_multivalue with other default"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        record.set_multivalue('value', "test")

        value, = ModelValue.search([])
        self.assertEqual(value.value_default, "other default")

    @with_transaction()
    def test_set_multivalue_many2one(self):
        "Test set_multivalue for Many2One"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')
        Target = pool.get('test.model_multivalue.target')

        record = ModelMultiValue()
        record.save()
        target = Target(name="Test")
        target.save()
        record.set_multivalue('value_many2one', target)

        value, = ModelValue.search([])
        self.assertEqual(value.record, record)
        self.assertEqual(value.value_many2one, target)

    @with_transaction()
    def test_set_multivalue_multiselection(self):
        "Test set_multivalue for MultiSelection"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')

        record = ModelMultiValue()
        record.save()
        record.set_multivalue('value_multiselection', ("foo", "bar"))

        value, = ModelValue.search([])
        self.assertEqual(value.record, record)
        self.assertEqual(value.value_multiselection, ('bar', 'foo'))

    @with_transaction()
    def test_set_multivalue_reference(self):
        "Test set_multivalue for Reference"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        ModelValue = pool.get('test.model_multivalue.value')
        Target = pool.get('test.model_multivalue.target')

        target = Target(name="Target")
        target.save()
        record = ModelMultiValue()
        record.save()
        record.set_multivalue('value_reference', target)

        value, = ModelValue.search([])
        self.assertEqual(value.record, record)
        self.assertEqual(value.value_reference, target)

    @with_transaction()
    def test_multivalue_setter(self):
        "Test multivalue setter"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')

        record, = ModelMultiValue.create([{
                    'value': "setter",
                    }])

        self.assertEqual(record.get_multivalue('value'), "setter")

    @with_transaction()
    def test_multivalue_getter(self):
        "Test multivalue getter"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')

        record = ModelMultiValue(value="getter")
        record.save()

        read, = ModelMultiValue.read([record.id], ['value'])
        self.assertEqual(read['value'], "getter")

    @with_transaction()
    def test_multivalue_getter_reference(self):
        "Test multivalue getter for Reference"
        pool = Pool()
        ModelMultiValue = pool.get('test.model_multivalue')
        Target = pool.get('test.model_multivalue.target')

        target = Target(name="Target")
        target.save()
        record = ModelMultiValue(value_reference=target)
        record.save()

        read, = ModelMultiValue.read([record.id], ['value_reference'])
        self.assertEqual(
            read['value_reference'],
            'test.model_multivalue.target,%s' % target.id)
