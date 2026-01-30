# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

from trytond.pool import Pool
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)
from trytond.transaction import Transaction


class FieldFunctionTestCase(TestCase):
    "Test Field Function"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
    def test_getter(self):
        "Test getter"
        pool = Pool()
        Model = pool.get('test.function.getter')

        record = Model()
        record.save()

        self.assertEqual(record.function_class, "class")
        self.assertEqual(record.function_class_names, "class names")
        self.assertEqual(record.function_instance, "instance")
        self.assertEqual(record.function_instance_names, "instance names")

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

    @with_transaction()
    def test_no_getter(self):
        "Test no getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter')

        record = Model(value=42)
        record.save()

        self.assertEqual(record.value_inc, 43)

    @with_transaction()
    def test_no_getter_no_column(self):
        "Test no column without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter')

        table_handler = Model.__table_handler__()

        self.assertFalse(table_handler.column_exist('value_inc'))

    @with_transaction()
    def test_no_getter_search(self):
        "Test search without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter')

        record = Model(value=42)
        record.save()

        result = Model.search([('value_inc', '=', 43)])
        self.assertEqual(result, [record])

    @with_transaction()
    def test_no_getter_order(self):
        "Test order without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter')

        Model.create([{'value': i} for i in range(10)])

        asc = Model.search([], order=[('value_inc', 'ASC')])
        asc = [r.value_inc for r in asc]
        desc = Model.search([], order=[('value_inc', 'DESC')])
        desc = [r.value_inc for r in desc]

        self.assertEqual(asc, sorted(asc))
        self.assertEqual(desc, sorted(asc, reverse=True))

    @with_transaction()
    def test_no_getter_relation(self):
        "Test no getter with relation"
        pool = Pool()
        Model = pool.get('test.function.no_getter.relation')
        Target = pool.get('test.function.no_getter.target')

        target = Target(name="Test")
        target.save()
        record = Model(target=target)
        record.save()

        self.assertEqual(record.target_name, "Test")
        self.assertEqual(record.target_target, target)

    @with_transaction()
    def test_no_getter_search_relation(self):
        "Test search on relation without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter.relation')
        Target = pool.get('test.function.no_getter.target')

        target = Target(name="Test")
        target.save()
        record = Model(target=target)
        record.save()

        result = Model.search([('target_name', '=', "Test")])

        self.assertEqual(result, [record])

    @with_transaction()
    def test_no_getter_search_relation_dotted(self):
        "Test search on dotted relation without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter.relation')
        Target = pool.get('test.function.no_getter.target')

        target = Target(name="Test")
        target.save()
        record = Model(target=target)
        record.save()

        result = Model.search([('target_target.name', '=', "Test")])

        self.assertEqual(result, [record])

    @with_transaction()
    def test_no_getter_order_relation(self):
        "Test order on relation without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter.relation')
        Target = pool.get('test.function.no_getter.target')

        for i in range(10):
            target = Target(name=str(i))
            target.save()
            record = Model(target=target)
            record.save()

        asc = Model.search([], order=[('target_name', 'ASC')])
        asc = [r.target_name for r in asc]
        desc = Model.search([], order=[('target_name', 'DESC')])
        desc = [r.target_name for r in desc]

        self.assertEqual(asc, sorted(asc))
        self.assertEqual(desc, sorted(asc, reverse=True))

    @with_transaction()
    def test_no_getter_order_relation_dotted(self):
        "Test order on dotted relation without getter"
        pool = Pool()
        Model = pool.get('test.function.no_getter.relation')
        Target = pool.get('test.function.no_getter.target')

        for i in range(10):
            target = Target(name=str(i))
            target.save()
            record = Model(target=target)
            record.save()

        asc = Model.search([], order=[('target_target.name', 'ASC')])
        asc = [r.target_target.name for r in asc]
        desc = Model.search([], order=[('target_target.name', 'DESC')])
        desc = [r.target_target.name for r in desc]

        self.assertEqual(asc, sorted(asc))
        self.assertEqual(desc, sorted(asc, reverse=True))
