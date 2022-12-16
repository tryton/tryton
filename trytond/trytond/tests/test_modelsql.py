# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest
import time
from unittest.mock import patch, call

from trytond import backend
from trytond.exceptions import ConcurrencyException
from trytond.model.exceptions import (
    RequiredValidationError, SQLConstraintError)
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class ModelSQLTestCase(unittest.TestCase):
    'Test ModelSQL'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_read(self):
        "Test simple read"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        foo, bar = Model.create([{'name': "Foo"}, {'name': "Bar"}])
        values = Model.read([foo.id, bar.id], ['name'])

        self.assertEqual(
            sorted(values, key=lambda v: v['id']),
            [{'id': foo.id, 'name': "Foo"}, {'id': bar.id, 'name': "Bar"}])

    @with_transaction()
    def test_read_context_id(self):
        "Test read with ID in context of field"
        pool = Pool()
        Model = pool.get('test.modelsql.read.context_id')

        record, = Model.create([{'name': "Record"}])
        values = Model.read([record.id], ['name'])

        self.assertEqual(values, [{'id': record.id, 'name': "Record"}])

    @with_transaction()
    def test_read_related_2one(self):
        "Test read with related Many2One"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target, = Target.create([{'name': "Target"}])
        record, = Model.create([{'target': target.id}])
        values = Model.read([record.id], ['target.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'target.': {
                        'id': target.id,
                        'name': "Target",
                        },
                    }])

    @with_transaction()
    def test_read_related_2one_empty(self):
        "Test read with empty related Many2One"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        record, = Model.create([{'target': None}])
        values = Model.read([record.id], ['target.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'target.': None,
                    }])

    @with_transaction()
    def test_read_related_reference(self):
        "Test read with related Reference"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target, = Target.create([{'name': "Target"}])
        record, = Model.create([{'reference': str(target)}])
        values = Model.read([record.id], ['reference.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'reference.': {
                        'id': target.id,
                        'name': "Target",
                        },
                    }])

    @with_transaction()
    def test_read_related_reference_empty(self):
        "Test read with empty related Reference"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        record, = Model.create([{'name': "Foo", 'reference': None}])
        values = Model.read([record.id], ['reference.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'reference.': None,
                    }])

    @with_transaction()
    def test_read_related_2many(self):
        "Test read with related One2Many"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target, = Target.create([{'name': "Target"}])
        record, = Model.create(
            [{'targets': [('add', [target.id])]}])
        values = Model.read([record.id], ['targets.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'targets.': [{
                            'id': target.id,
                            'name': "Target",
                            }],
                    }])

    @with_transaction()
    def test_read_related_2many_empty(self):
        "Test read with empty related One2Many"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        record, = Model.create(
            [{'targets': None}])
        values = Model.read([record.id], ['targets.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'targets.': [],
                    }])

    @with_transaction()
    def test_read_related_2many_multiple(self):
        "Test read with multiple related One2Many"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target1, target2 = Target.create([
                {'name': "Target 1"},
                {'name': "Target 2"}])
        record, = Model.create(
            [{'targets': [('add', [target1.id, target2.id])]}])
        values = Model.read([record.id], ['targets.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'targets.': [{
                            'id': target1.id,
                            'name': "Target 1",
                            }, {
                            'id': target2.id,
                            'name': "Target 2",
                            }],
                    }])

    @with_transaction()
    def test_read_related_mixed(self):
        "Test read mixed related"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target1, target2, target3 = Target.create([
                {'name': "Target 1"},
                {'name': "Target 2"},
                {'name': "Target 3"}])
        record1, record2 = Model.create([{
                    'name': "Foo",
                    'target': target1.id,
                    'targets': [('add', [target1.id, target2.id])],
                    }, {
                    'name': "Bar",
                    'reference': str(target2),
                    'targets': [('add', [target3.id])],
                    }])
        values = Model.read(
            [record1.id, record2.id],
            ['name', 'target', 'target.name', 'targets', 'targets.name'])

        self.assertEqual(
            sorted(values, key=lambda v: v['id']), [{
                    'id': record1.id,
                    'name': "Foo",
                    'target': target1.id,
                    'target.': {
                        'id': target1.id,
                        'name': "Target 1",
                        },
                    'targets': (target1.id, target2.id),
                    'targets.': [{
                            'id': target1.id,
                            'name': "Target 1",
                            }, {
                            'id': target2.id,
                            'name': "Target 2",
                            }],
                    }, {
                    'id': record2.id,
                    'name': "Bar",
                    'target': None,
                    'target.': None,
                    'targets': (target3.id,),
                    'targets.': [{
                            'id': target3.id,
                            'name': "Target 3",
                            }],
                    }])

    @with_transaction()
    def test_read_related_nested(self):
        "Test read with nested related"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target, = Target.create([{'name': "Target"}])
        record, = Model.create(
            [{'name': "Record", 'targets': [('add', [target.id])]}])
        values = Model.read([record.id], ['targets.parent.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'targets.': [{
                            'id': target.id,
                            'parent.': {
                                'id': record.id,
                                'name': "Record",
                                },
                            }],
                    }])

    @unittest.skipIf(backend.name == 'sqlite',
        'SQLite not concerned because tryton don\'t set "NOT NULL"'
        'constraint: "ALTER TABLE" don\'t support NOT NULL constraint'
        'without default value')
    @with_transaction()
    def test_required_field_missing(self):
        'Test error message when a required field is missing'
        pool = Pool()
        Modelsql = pool.get('test.modelsql')
        transaction = Transaction()

        fields = {
            'desc': '',
            'integer': 0,
            }
        for key, value in fields.items():
            try:
                Modelsql.create([{key: value}])
            except RequiredValidationError as err:
                # message must not quote key
                msg = "'%s' not missing but quoted in error: '%s'" % (key,
                        err.message)
                self.assertTrue(key not in err.message, msg)
            else:
                self.fail('RequiredValidationError should be caught')
            transaction.rollback()

    @with_transaction()
    def test_check_timestamp(self):
        'Test check timestamp'
        pool = Pool()
        ModelsqlTimestamp = pool.get('test.modelsql.timestamp')
        transaction = Transaction()
        # transaction must be committed between each changes otherwise NOW()
        # returns always the same timestamp.
        record, = ModelsqlTimestamp.create([{}])
        transaction.commit()

        timestamp = ModelsqlTimestamp.read([record.id],
            ['_timestamp'])[0]['_timestamp']

        if backend.name == 'sqlite':
            # timestamp precision of sqlite is the second
            time.sleep(1)

        transaction.timestamp[str(record)] = timestamp
        ModelsqlTimestamp.write([record], {})
        transaction.commit()

        transaction.timestamp[str(record)] = timestamp
        self.assertRaises(ConcurrencyException,
            ModelsqlTimestamp.write, [record], {})

        transaction.timestamp[str(record)] = timestamp
        self.assertRaises(ConcurrencyException,
            ModelsqlTimestamp.delete, [record])

        transaction.timestamp[str(record)] = None
        ModelsqlTimestamp.write([record], {})
        transaction.commit()

        transaction.timestamp.pop(str(record), None)
        ModelsqlTimestamp.write([record], {})
        transaction.commit()
        ModelsqlTimestamp.delete([record])
        transaction.commit()

    @with_transaction()
    def test_create_field_set(self):
        'Test field.set in create'
        pool = Pool()
        Model = pool.get('test.modelsql.field_set')

        with patch.object(Model, 'set_field') as setter:
            records = Model.create([{'field': 1}])
            setter.assert_called_with(records, 'field', 1)

        # Different values are not grouped
        with patch.object(Model, 'set_field') as setter:
            records = Model.create([{'field': 1}, {'field': 2}])
            setter.assert_has_calls([
                    call([records[0]], 'field', 1),
                    call([records[1]], 'field', 2),
                    ])

        # Same values are grouped in one call
        with patch.object(Model, 'set_field') as setter:
            records = Model.create([{'field': 1}, {'field': 1}])
            setter.assert_called_with(records, 'field', 1)

        # Mixed values are grouped per value
        with patch.object(Model, 'set_field') as setter:
            records = Model.create([{'field': 1}, {'field': 2}, {'field': 1}])
            setter.assert_has_calls([
                    call([records[0], records[2]], 'field', 1),
                    call([records[1]], 'field', 2),
                    ])

    @with_transaction()
    def test_integrity_error_with_created_record(self):
        "Test integrity error with created record"
        pool = Pool()
        ParentModel = pool.get('test.modelsql.one2many')
        TargetModel = pool.get('test.modelsql.one2many.target')

        # Create target record without required name
        # to ensure create_records is filled to prevent raising
        # foreign_model_missing
        record = ParentModel()
        record.targets = [TargetModel()]
        with self.assertRaises(RequiredValidationError) as cm:
            record.save()
        err = cm.exception
        self.assertIn(TargetModel.name.string, err.message)
        self.assertIn(TargetModel.__doc__, err.message)

    @with_transaction()
    def test_null_ordering(self):
        'Test NULL ordering'
        pool = Pool()
        NullOrder = pool.get('test.modelsql.null_order')

        NullOrder.create([{
                    'integer': 1,
                    }, {
                    'integer': 3,
                    }, {
                    'integer': None,
                    }])
        integers = NullOrder.search([], order=[('integer', 'ASC NULLS FIRST')])
        self.assertListEqual([i.integer for i in integers], [None, 1, 3])

        integers = NullOrder.search(
            [], order=[('integer', 'DESC NULLS FIRST')])
        self.assertListEqual([i.integer for i in integers], [None, 3, 1])

        integers = NullOrder.search([], order=[('integer', 'ASC NULLS LAST')])
        self.assertListEqual([i.integer for i in integers], [1, 3, None])

        integers = NullOrder.search([], order=[('integer', 'DESC NULLS LAST')])
        self.assertListEqual([i.integer for i in integers], [3, 1, None])

    @with_transaction()
    def test_delete_translations(self):
        "Test delete record trigger delete of translations"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')
        record, = Model.create([{'name': "Translation"}])

        with patch.object(Translation, 'delete_ids') as delete_ids:
            Model.delete([record])

        delete_ids.assert_called_with(
            'test.modelsql.translation', 'model', [record.id])

    @with_transaction()
    def test_constraint_check(self):
        "Test check constraint"
        pool = Pool()
        Model = pool.get('test.modelsql.check')

        record, = Model.create([{'value': 50}])

        self.assertTrue(record.id)

    @with_transaction()
    def test_constraint_check_null(self):
        "Test check constraint with null"
        pool = Pool()
        Model = pool.get('test.modelsql.check')

        record, = Model.create([{'value': None}])

        self.assertTrue(record.id)

    @with_transaction()
    def test_constraint_check_invalid(self):
        "Test invalid check constraint"
        pool = Pool()
        Model = pool.get('test.modelsql.check')

        with self.assertRaises(SQLConstraintError):
            Model.create([{'value': 10}])

    @with_transaction()
    def test_constraint_unique(self):
        "Test unique constraint"
        pool = Pool()
        Model = pool.get('test.modelsql.unique')

        records = Model.create([{'value': 1}, {'value': 2}])

        self.assertEqual(len(records), 2)

    @with_transaction()
    def test_constraint_unique_null(self):
        "Test unique constraint with null"
        pool = Pool()
        Model = pool.get('test.modelsql.unique')

        records = Model.create([{'value': None}, {'value': None}])

        self.assertEqual(len(records), 2)

    @with_transaction()
    def test_constraint_unique_invalid(self):
        "Test invalid unique constraint"
        pool = Pool()
        Model = pool.get('test.modelsql.unique')

        with self.assertRaises(SQLConstraintError):
            Model.create([{'value': 42}, {'value': 42}])

    @with_transaction()
    def test_constraint_exclude(self):
        "Test exclude constraint"
        pool = Pool()
        Model = pool.get('test.modelsql.exclude')

        records = Model.create([{'value': 1}, {'value': 2}])

        self.assertEqual(len(records), 2)

    @with_transaction()
    def test_constraint_exclude_exclusion(self):
        "Test exclude constraint exclusion"
        pool = Pool()
        Model = pool.get('test.modelsql.exclude')

        records = Model.create([{'value': 1, 'condition': False}] * 2)

        self.assertEqual(len(records), 2)

    @with_transaction()
    def test_constraint_exclude_exclusion_mixed(self):
        "Test exclude constraint exclusion mixed"
        pool = Pool()
        Model = pool.get('test.modelsql.exclude')

        records = Model.create([
                {'value': 1, 'condition': False},
                {'value': 1, 'condition': True},
                ])

        self.assertEqual(len(records), 2)

    @with_transaction()
    def test_constraint_exclude_invalid(self):
        "Test invalid exclude constraint"
        pool = Pool()
        Model = pool.get('test.modelsql.exclude')

        with self.assertRaises(SQLConstraintError):
            Model.create([{'value': 42}, {'value': 42}])

    @unittest.skipIf(backend.name == 'sqlite',
        'SQLite does not have lock at table level but on file')
    @with_transaction()
    def test_lock(self):
        "Test lock"
        pool = Pool()
        Model = pool.get('test.modelsql.lock')
        transaction = Transaction()
        record_id = Model.create([{}])[0].id
        transaction.commit()

        with transaction.new_transaction():
            record = Model(record_id)
            record.lock()
            with transaction.new_transaction():
                record = Model(record_id)
                with self.assertRaises(backend.DatabaseOperationalError):
                    record.lock()


class ModelSQLTranslationTestCase(unittest.TestCase):
    "Test ModelSQL translation"
    default_language = 'fr'
    other_language = 'en'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')
        cls.setup_language()

    @classmethod
    @with_transaction()
    def setup_language(cls):
        pool = Pool()
        Language = pool.get('ir.lang')
        Configuration = pool.get('ir.configuration')

        default, = Language.search([('code', '=', cls.default_language)])
        default.translatable = True
        default.save()

        other, = Language.search([('code', '=', cls.other_language)])
        other.translatable = True
        other.save()

        config = Configuration(1)
        config.language = cls.default_language
        config.save()

        Transaction().commit()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.restore_language()

    @classmethod
    @with_transaction()
    def restore_language(cls):
        pool = Pool()
        Language = pool.get('ir.lang')
        Configuration = pool.get('ir.configuration')

        english, = Language.search([('code', '=', 'en')])
        english.translatable = True
        english.save()

        config = Configuration(1)
        config.language = 'en'
        config.save()

        Language.write(Language.search([('code', '!=', 'en')]), {
                'translatable': False,
                })

        Transaction().commit()

    @with_transaction()
    def test_create_default_language(self):
        "Test create default language"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(language=self.default_language):
            record, = Model.create([{'name': "Foo"}])
        translation, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ])

        self.assertEqual(translation.src, "Foo")
        self.assertEqual(translation.value, "Foo")
        self.assertEqual(translation.lang, self.default_language)
        self.assertFalse(translation.fuzzy)

    @with_transaction()
    def test_create_other_language(self):
        "Test create other language"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(language=self.other_language):
            record, = Model.create([{'name': "Bar"}])
        translation, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ])

        self.assertEqual(translation.src, "Bar")
        self.assertEqual(translation.value, "Bar")
        self.assertEqual(translation.lang, self.other_language)
        self.assertFalse(translation.fuzzy)

    @with_transaction()
    def test_write_default_language(self):
        "Test write default language"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.default_language):
            Model.write([record], {'name': "Bar"})
        translation, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ])

        self.assertEqual(translation.src, "Bar")
        self.assertEqual(translation.value, "Bar")
        self.assertEqual(translation.lang, self.default_language)
        self.assertFalse(translation.fuzzy)

    @with_transaction()
    def test_write_other_language(self):
        "Test write other language"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})
        default, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ('lang', '=', self.default_language),
                ])
        other, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ('lang', '=', self.other_language),
                ])

        self.assertEqual(default.src, "Foo")
        self.assertEqual(default.value, "Foo")
        self.assertFalse(default.fuzzy)
        self.assertEqual(other.src, "Foo")
        self.assertEqual(other.value, "Bar")
        self.assertFalse(other.fuzzy)

    @with_transaction()
    def test_write_default_language_with_other_language(self):
        "Test write default language with other language"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})
        with Transaction().set_context(language=self.default_language):
            Model.write([record], {'name': "FooBar"})
        default, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ('lang', '=', self.default_language),
                ])
        other, = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ('lang', '=', self.other_language),
                ])

        self.assertEqual(default.src, "FooBar")
        self.assertEqual(default.value, "FooBar")
        self.assertFalse(default.fuzzy)
        self.assertEqual(other.src, "FooBar")
        self.assertEqual(other.value, "Bar")
        self.assertTrue(other.fuzzy)

    @with_transaction()
    def test_delete(self):
        "Test delete"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})
        before_translations = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ])
        Model.delete([record])
        after_translations = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ])

        self.assertTrue(before_translations)
        self.assertFalse(after_translations)

    @with_transaction()
    def test_read(self):
        "Test read translations"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')

        with Transaction().set_context(language=self.default_language):
            record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})
            other = Model(record.id)

        self.assertEqual(record.name, "Foo")
        self.assertEqual(other.name, "Bar")

    @with_transaction()
    def test_read_last_translation(self):
        "Test read last translation record"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(language=self.default_language):
            record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})
            other = Model(record.id)

        translation, = Translation.search([
                ('lang', '=', self.other_language),
                ('name', '=', 'test.modelsql.translation,name'),
                ('type', '=', 'model'),
                ('res_id', '=', record.id),
                ])
        Translation.copy([translation], default={'value': "Baz"})

        self.assertEqual(record.name, "Foo")
        self.assertEqual(other.name, "Baz")

    @with_transaction()
    def test_order_empty_translation(self):
        "Test order on empty translation value"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(language=self.default_language):
            records = Model.create(
                [{'name': "A"}, {'name': "B"}, {'name': "C"}])

        translation, = Translation.search([
                ('lang', '=', self.default_language),
                ('name', '=', 'test.modelsql.translation,name'),
                ('type', '=', 'model'),
                ('res_id', '=', records[1].id),
                ])
        translation.value = ''
        translation.save()

        with Transaction().set_context(language=self.default_language):
            self.assertEqual(
                Model.search([], order=[('name', 'ASC')]),
                records)

    @with_transaction()
    def test_search_unique_result(self):
        "Test unique result on search"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(language=self.default_language):
            record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})

        translation, = Translation.search([
                ('lang', '=', self.other_language),
                ('name', '=', 'test.modelsql.translation,name'),
                ('type', '=', 'model'),
                ('res_id', '=', record.id),
                ])
        Translation.copy([translation], default={'value': "Baz"})

        with Transaction().set_context(language=self.other_language):
            self.assertEqual(
                Model.search([('name', 'like', 'Ba%')]),
                [record])
            self.assertEqual(
                Model.search([], order=[('name', 'DESC')]),
                [record])

    @unittest.skipIf(backend.name != 'postgresql',
        "Only PostgreSQL support DISTINCT ON")
    @with_transaction()
    def test_search_last_translation(self):
        "Test unique result on search"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(language=self.default_language):
            record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})

        translation, = Translation.search([
                ('lang', '=', self.other_language),
                ('name', '=', 'test.modelsql.translation,name'),
                ('type', '=', 'model'),
                ('res_id', '=', record.id),
                ])
        Translation.copy([translation], default={'value': "Baz"})

        with Transaction().set_context(language=self.other_language):
            self.assertEqual(
                Model.search([('name', '=', 'Baz')]),
                [record])
            self.assertEqual(
                Model.search([('name', '=', 'Bar')]),
                [])

    @with_transaction()
    def test_search_fill_transaction_cache(self):
        "Test search fill the transaction cache"
        pool = Pool()
        Model = pool.get('test.modelsql.search')
        Model.create([{'name': "Foo"}])

        record, = Model.search([])
        cache = Transaction().get_cache()[Model.__name__]

        self.assertIn(record.id, cache)
        self.assertEqual(cache[record.id]['name'], "Foo")
        self.assertNotIn('_timestamp', cache[record.id])


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModelSQLTestCase))
    suite_.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ModelSQLTranslationTestCase))
    return suite_
