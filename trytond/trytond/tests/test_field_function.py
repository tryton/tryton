# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from unittest.mock import patch

from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction


class FieldFunctionTestCase(unittest.TestCase):
    "Test Field Function"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_definition(self):
        pool = Pool()
        Model = pool.get('test.function.definition')

        definition = Model.function.definition(Model, 'en')
        self.assertEqual(definition, {
                'context': '{}',
                'loading': 'lazy',
                'name': 'function',
                'on_change': [],
                'on_change_with': [],
                'readonly': True,
                'required': False,
                'states': '{}',
                'type': 'integer',
                'domain': '[]',
                'searchable': True,
                'sortable': False,
                'help': '',
                'string': 'Integer',
                })

    @with_transaction()
    def test_accessor(self):
        "Test accessing field on unsaved instance"
        pool = Pool()
        Model = pool.get('test.function.accessor')
        Target = pool.get('test.function.accessor.target')

        target = Target()
        target.save()
        record = Model()
        record.target = target

        self.assertEqual(record.function, target)

    @with_transaction()
    def test_getter_context(self):
        "Test getter context"
        pool = Pool()
        Model = pool.get('test.function.getter_context')

        record = Model()
        record.save()

        with Transaction().set_context(language='en', test='foo'):
            record = Model(record.id)

        self.assertEqual(record.function_with_context, 'en - foo')
        self.assertEqual(record.function_without_context, 'en - empty')

    @with_transaction()
    def test_getter_cached_readonly_transaction(self):
        "Test getter cached in read only transaction"
        pool = Pool()
        Model = pool.get('test.function.getter_context')

        with Transaction().new_transaction(readonly=True), \
                patch.object(Model, 'getter') as getter:
            record, = Model.search([], limit=1)
            record.function_with_context
            record.function_without_context
            self.assertEqual(getter.call_count, 2)

            getter.reset_mock()
            with Transaction().set_context(test='foo'):
                record = Model(record.id)
            record.function_with_context
            record.function_without_context
            self.assertEqual(getter.call_count, 1)

            getter.reset_mock()
            # Change transaction key context
            with Transaction().set_context(language='en'):
                record = Model(record.id)
            record.function_with_context
            record.function_without_context
            self.assertEqual(getter.call_count, 2)

    @with_transaction()
    def test_getter_local_cache(self):
        "Test getter use local cache"
        pool = Pool()
        Model = pool.get('test.function.getter_local_cache')

        record = Model()
        record.save()
        with patch.object(Model, 'get_function1', autospec=True) as getter:
            getter.return_value = 'test'

            Model.read([record.id], ['function1', 'function2'])

            self.assertEqual(getter.call_count, 1)
