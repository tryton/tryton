# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import random
import time
import unittest
from unittest.mock import call, patch

from trytond import backend
from trytond.exceptions import ConcurrencyException
from trytond.model.exceptions import (
    AccessError, ForeignKeyError, RequiredValidationError, SQLConstraintError)
from trytond.model.modelsql import split_subquery_domain
from trytond.pool import Pool
from trytond.tests.test_tryton import (
    CONTEXT, DB_NAME, USER, activate_module, with_transaction)
from trytond.transaction import Transaction, TransactionError


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
    def test_read_no_exist(self):
        "Test read ids that does not exist"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        with self.assertRaises(AccessError):
            Model.read([42], ['name'])

    @with_transaction()
    def test_read_context_id(self):
        "Test read with ID in context of field"
        pool = Pool()
        Model = pool.get('test.modelsql.read.context_id')

        record, = Model.create([{'name': "Record"}])
        values = Model.read([record.id], ['name'])

        self.assertEqual(values, [{'id': record.id, 'name': "Record"}])

    @with_transaction()
    def test_read_function_field_bigger_than_cache(self):
        "Test reading a Function field on a list bigger then the cache size"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        records = Model.create([{'name': str(i)} for i in range(10)])
        records_created = {m.id: m.name for m in records}
        record_ids = [r.id for r in records]
        random.shuffle(record_ids)

        with Transaction().set_context(_record_cache_size=2):
            records_read = {r['id']: r['rec_name']
                for r in Model.read(record_ids, ['rec_name'])}
            self.assertEqual(records_read, records_created)

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
    def test_read_related_invalid_reference(self):
        "Test read with related invalid Reference"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        record, = Model.create(
            [{'reference': 'test.modelsql.read.target,None'}])
        values = Model.read([record.id], ['reference.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'reference.': None,
                    }])

    @with_transaction()
    def test_read_related_deleted_reference(self):
        "Test read with related deleted Reference"
        pool = Pool()
        Model = pool.get('test.modelsql.read')
        Target = pool.get('test.modelsql.read.target')

        target, = Target.create([{'name': "Target"}])
        record, = Model.create([{'reference': str(target)}])
        Target.delete([target])
        values = Model.read([record.id], ['reference.name'])

        self.assertEqual(values, [{
                    'id': record.id,
                    'reference.': None,
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

    @with_transaction()
    def test_read_limit(self):
        "Test that we limit the number or related records read"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        model, = Model.create([{
                    'name': 'Record',
                    'targets': [
                        ('create', [{'name': str(i)} for i in range(10)]),
                        ]
                    }])

        values, = Model.read([model.id], ['targets.name'])
        self.assertTrue(all('id' in t and 'name' in t
                for t in values['targets.']))

        with Transaction().set_context(related_read_limit=4):
            values, = Model.read([model.id], ['targets.name'])
            self.assertTrue(all('id' in t and 'name' in t
                    for t in values['targets.'][:4]))
            self.assertTrue(all('id' in t and len(t) == 1
                    for t in values['targets.'][4:]))

    @with_transaction()
    def test_read_limit_only_limit_related(self):
        "Test that we don't limit reading records with related_read_limit"
        pool = Pool()
        Model = pool.get('test.modelsql.read')

        records = Model.create([
                {
                    'name': f'Record {i}',
                    'targets': [
                        ('create', [{'name': str(i)} for i in range(10)]),
                        ]
                    } for i in range(10)])
        with Transaction().set_context(related_read_limit=4):
            values = Model.read(
                [r.id for r in records], ['name', 'targets.name'])
            self.assertTrue(all('id' in v and 'name' in v for v in values))
            self.assertTrue(all(len(v['targets.']) == 10 for v in values))

    @with_transaction()
    def test_read_limit_caching(self):
        "Test that limiting the related records read plays nice with caching"
        pool = Pool()
        Model = pool.get('test.modelsql.read.limit')

        records = Model.create([
                {
                    'name': f'Record {i}',
                    'targets': [
                        ('create', [{'name': str(j), 'integer': j}
                                for j in range(1, i + 1)]),
                        ],
                    } for i in range(10)])

        with Transaction().set_context(read_limit=4):
            values = Model.read(
                [r.id for r in records],
                ['name', 'targets.name', 'sum_targets'])
            computed = {r['name']: r['sum_targets'] for r in values}
            expected = {f'Record {i}': i * (i + 1) // 2 for i in range(10)}
            self.assertEqual(computed, expected)

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
    def test_create(self):
        "Test create record"
        pool = Pool()
        Model = pool.get('test.modelsql.create')

        m1, = Model.create([{
                    'char': "Value 1",
                    }])

        self.assertTrue(m1.id)
        self.assertEqual(m1.char, "Value 1")

    def test_create_without_returning(self):
        "Test create record without returning"
        with patch.object(backend.Database, 'has_returning') as returning:
            returning.return_value = False
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                pool = Pool()
                Model = pool.get('test.modelsql.create')

                m1, = Model.create([{
                            'char': "Value 1",
                            }])

                self.assertTrue(m1.id)
                self.assertEqual(m1.char, "Value 1")

    @with_transaction()
    def test_create_many_records(self):
        "Test create many records"
        pool = Pool()
        Model = pool.get('test.modelsql.create')

        # The order of the keys shouldn't matter
        foo, bar, baz = Model.create([{
                    'char': "Foo",
                    'integer': 2
                    }, {
                    'integer': 4,
                    'char': "Bar"
                    }, {
                    'char': "Baz"
                    }])

        self.assertEqual(foo.char, "Foo")
        self.assertEqual(foo.integer, 2)
        self.assertEqual(bar.char, "Bar")
        self.assertEqual(bar.integer, 4)
        self.assertEqual(baz.char, "Baz")
        self.assertEqual(baz.integer, None)

    def test_create_many_records_without_multirow_insert(self):
        "Test create many records without multirow insert"
        with patch.object(backend.Database, 'has_multirow_insert') as multirow:
            multirow.return_value = False
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                pool = Pool()
                Model = pool.get('test.modelsql.create')

                m1, m2 = Model.create([{
                            'char': "Value 1",
                            }, {
                            'char': "Value 2",
                            }])

                self.assertTrue(m1.id)
                self.assertEqual(m1.char, "Value 1")
                self.assertTrue(m2.id)
                self.assertEqual(m2.char, "Value 2")
                self.assertLess(m1.id, m2.id)

    def test_create_many_without_returning_and_multirow_insert(self):
        "Test create record without returning an multirow insert"
        with patch.object(backend.Database, 'has_returning') as returning, \
                patch.object(
                    backend.Database, 'has_multirow_insert') as multirow:
            returning.return_value = False
            multirow.return_value = False
            with Transaction().start(DB_NAME, USER, context=CONTEXT):
                pool = Pool()
                Model = pool.get('test.modelsql.create')

                m1, m2 = Model.create([{
                            'char': "Value 1",
                            }, {
                            'char': "Value 2",
                            }])

                self.assertTrue(m1.id)
                self.assertEqual(m1.char, "Value 1")
                self.assertTrue(m2.id)
                self.assertEqual(m2.char, "Value 2")
                self.assertLess(m1.id, m2.id)

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
    def test_write_no_exist(self):
        "Test write on ids that does not exist"
        pool = Pool()
        Model = pool.get('test.modelsql.write')

        with self.assertRaises(AccessError):
            Model.write([Model(42)], {'name': 'foo'})

    @with_transaction()
    def test_delete_no_exist(self):
        "Test delete ids that does not exist"
        pool = Pool()
        Model = pool.get('test.modelsql.delete')

        Model.delete([Model(42)])

    @with_transaction()
    def test_foreign_key_cascade(self):
        "Test Foreign key on delete cascade"
        pool = Pool()
        Model = pool.get('test.modelsql.fk')
        Target = pool.get('test.modelsql.fk.target')

        target = Target()
        target.save()
        record = Model(target_cascade=target)
        record.save()

        Target.delete([target])

        self.assertFalse(Model.search([]))

    @with_transaction()
    def test_foreign_key_cascade_tree(self):
        "Test tree Foreign key on delete cascade"
        pool = Pool()
        Model = pool.get('test.modelsql.fk.tree')

        parent = Model()
        parent.save()
        child = Model(parent_cascade=parent)
        child.save()

        Model.delete([parent])

        self.assertFalse(Model.search([]))

    @with_transaction()
    def test_foreign_key_null(self):
        "Test Foreign key on delete set null"
        pool = Pool()
        Model = pool.get('test.modelsql.fk')
        Target = pool.get('test.modelsql.fk.target')

        target = Target()
        target.save()
        record = Model(target_null=target)
        record.save()

        Target.delete([target])

        self.assertFalse(record.target_null)

    @with_transaction()
    def test_foreign_key_null_tree(self):
        "Test tree Foreign key on delete set null"
        pool = Pool()
        Model = pool.get('test.modelsql.fk.tree')

        parent = Model()
        parent.save()
        child = Model(parent_null=parent)
        child.save()

        Model.delete([parent])

        self.assertFalse(child.parent_null)

    @with_transaction()
    def test_foreign_key_null_required(self):
        "Test Foreign key on delete set null required"
        pool = Pool()
        Model = pool.get('test.modelsql.fk')
        Target = pool.get('test.modelsql.fk.target')

        Model.target_null.required = True
        self.addCleanup(setattr, Model.target_null, 'required', False)

        target = Target()
        target.save()
        record = Model(target_null=target)
        record.save()

        with self.assertRaises(ForeignKeyError) as cm:
            Target.delete([target])
        err = cm.exception
        self.assertIn(Model.target_null.string, err.message)
        self.assertIn(Model.__doc__, err.message)

    @with_transaction()
    def test_foreign_key_restrict(self):
        "Test Foreign key on delete restrict"
        pool = Pool()
        Model = pool.get('test.modelsql.fk')
        Target = pool.get('test.modelsql.fk.target')

        target = Target()
        target.save()
        record = Model(target_restrict=target)
        record.save()

        with self.assertRaises(ForeignKeyError) as cm:
            Target.delete([target])
        err = cm.exception
        self.assertIn(Model.target_restrict.string, err.message)
        self.assertIn(Model.__doc__, err.message)

    @with_transaction()
    def test_foreign_key_restrict_inactive(self):
        "Test inactive Foreign key on delete restrict"
        pool = Pool()
        Model = pool.get('test.modelsql.fk')
        Target = pool.get('test.modelsql.fk.target')

        target = Target()
        target.save()
        record = Model(target_restrict=target, active=False)
        record.save()

        with self.assertRaises(ForeignKeyError) as cm:
            Target.delete([target])
        err = cm.exception
        self.assertIn(Model.target_restrict.string, err.message)
        self.assertIn(Model.__doc__, err.message)

    @with_transaction()
    def test_foreign_key_restrict_tree(self):
        "Test tree Foreign key on delete restrict"
        pool = Pool()
        Model = pool.get('test.modelsql.fk.tree')

        parent = Model()
        parent.save()
        child = Model(parent_restrict=parent)
        child.save()

        with self.assertRaises(ForeignKeyError):
            Model.delete([parent])

    @with_transaction()
    def test_foreign_key_restrict_tree_branch_full(self):
        "Test tree Foreign key on delete restrict full branch"
        pool = Pool()
        Model = pool.get('test.modelsql.fk.tree')

        # Delete all records at a time
        in_max = Transaction().database.IN_MAX
        self.addCleanup(setattr, Transaction().database, 'IN_MAX', in_max)
        Transaction().database.IN_MAX = 2

        parent = Model()
        parent.save()
        child = Model(parent_restrict=parent)
        child.save()

        Model.delete([parent, child])

    @with_transaction()
    def test_foreign_key_restrict_tree_branch_grouped(self):
        "Test tree Foreign key on delete restrict grouped branch"
        pool = Pool()
        Model = pool.get('test.modelsql.fk.tree')

        # Delete one record at a time
        in_max = Transaction().database.IN_MAX
        self.addCleanup(setattr, Transaction().database, 'IN_MAX', in_max)
        Transaction().database.IN_MAX = 1

        parent = Model()
        parent.save()
        child = Model(parent_restrict=parent)
        child.save()

        Model.delete([parent, child])

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
    def test_record_lock(self):
        "Test record lock"
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

    @unittest.skipIf(backend.name == 'sqlite',
        'SQLite does not have lock at table level but on file')
    @with_transaction()
    def test_table_lock(self):
        "Test table lock"
        pool = Pool()
        Model = pool.get('test.modelsql.lock')
        transaction = Transaction()

        args1 = {}
        while True:
            with transaction.new_transaction(**args1):
                try:
                    Model.lock()
                except TransactionError as e:
                    e.fix(args1)
                    continue
                with self.assertRaises(
                        backend.DatabaseOperationalError):
                    args2 = {}
                    while True:
                        with transaction.new_transaction(**args2):
                            try:
                                Model.lock()
                            except TransactionError as e:
                                e.fix(args2)
                                continue
                            break
                break

    @with_transaction()
    def test_search_or_to_union(self):
        """
        Test searching for 'OR'-ed domain
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')

        Model.create([{
                    'name': 'A',
                    }, {
                    'name': 'B',
                    }, {
                    'name': 'C',
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', 'ilike', '%A%'),
            ('targets.name', 'ilike', '%A'),
            ]
        with patch('trytond.model.modelsql.split_subquery_domain') as no_split:
            # Mocking in order not to trigger the split
            no_split.side_effect = lambda d: (d, [])
            result_without_split = Model.search(domain)
            query_without_split = Model.search(domain, query=True)
        self.assertEqual(
            Model.search(domain),
            result_without_split)
        self.assertIn('UNION', str(Model.search(domain, query=True)))
        self.assertNotIn('UNION', str(query_without_split))

    @with_transaction()
    def test_search_or_to_union_with_in_clause(self):
        "Test searching for 'OR'-ed domain with in clause"
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')

        record, = Model.create([{
                    'name': "Foo",
                    'targets': [('create', [{
                                    'name': "Bar",
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', '=', 'Bar'),
            ('targets.id', 'in', [t.id for t in record.targets]),
            ]
        self.assertEqual(Model.search(domain), [record])

    @with_transaction()
    def test_search_or_to_union_order_eager_field(self):
        """
        Searching for 'OR'-ed domain mixed with ordering on an eager field
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')
        Target = pool.get('test.modelsql.search.or2union.target')

        target_a, target_b, target_c = Target.create([
                {'name': 'A'}, {'name': 'B'}, {'name': 'C'},
                ])
        model_a, model_b, model_c = Model.create([{
                    'name': 'A',
                    'target': target_a,
                    }, {
                    'name': 'B',
                    'target': target_b,
                    }, {
                    'name': 'C',
                    'target': target_c,
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', 'ilike', '%A%'),
            ('targets.name', 'ilike', '%A'),
            ]
        self.assertEqual(
            Model.search(domain, order=[('name', 'ASC')]),
            [model_a, model_c])
        self.assertEqual(
            Model.search(domain, order=[('name', 'DESC')]),
            [model_c, model_a])
        self.assertIn(
            'UNION',
            str(Model.search(domain, order=[('name', 'ASC')], query=True)))

    @with_transaction()
    def test_search_or_to_union_order_lazy_field(self):
        """
        Searching for 'OR'-ed domain mixed with ordering on a lazy field
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')
        Target = pool.get('test.modelsql.search.or2union.target')

        target_a, target_b, target_c = Target.create([
                {'name': 'A'}, {'name': 'B'}, {'name': 'C'},
                ])
        model_a, model_b, model_c = Model.create([{
                    'name': 'A',
                    'reference': str(target_a),
                    }, {
                    'name': 'B',
                    'reference': str(target_b),
                    }, {
                    'name': 'C',
                    'reference': str(target_c),
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', 'ilike', '%A%'),
            ('targets.name', 'ilike', '%A'),
            ]
        self.assertEqual(
            Model.search(domain, order=[('reference', 'ASC')]),
            [model_a, model_c])
        self.assertEqual(
            Model.search(domain, order=[('reference', 'DESC')]),
            [model_c, model_a])
        self.assertIn(
            'UNION', str(Model.search(
                    domain, order=[('reference', 'ASC')], query=True)))

    @with_transaction()
    def test_search_or_to_union_order_dotted_notation(self):
        """
        Searching for 'OR'-ed domain mixed with ordering on dotted field
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')
        Target = pool.get('test.modelsql.search.or2union.target')

        target_a, target_b, target_c = Target.create([
                {'name': 'A'}, {'name': 'B'}, {'name': 'C'},
                ])
        model_a, model_b, model_c = Model.create([{
                    'name': 'A',
                    'target': target_a,
                    }, {
                    'name': 'B',
                    'target': target_b,
                    }, {
                    'name': 'C',
                    'target': target_c,
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', 'ilike', '%A%'),
            ('targets.name', 'ilike', '%A'),
            ]
        self.assertEqual(
            Model.search(domain, order=[('target.name', 'ASC')]),
            [model_a, model_c])
        self.assertEqual(
            Model.search(domain, order=[('target.name', 'DESC')]),
            [model_c, model_a])
        self.assertNotIn(
            'UNION', str(Model.search(
                    domain, order=[('target.name', 'ASC')], query=True)))

    @with_transaction()
    def test_search_or_to_union_order_function(self):
        """
        Searching for 'OR'-ed domain mixed with ordering on a function
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')
        Target = pool.get('test.modelsql.search.or2union.target')

        target_a, target_b, target_c = Target.create([
                {'name': 'A'}, {'name': 'B'}, {'name': 'C'},
                ])
        model_a, model_b, model_c = Model.create([{
                    'name': 'A',
                    'target': target_a,
                    'integer': 0,
                    }, {
                    'name': 'B',
                    'target': target_b,
                    'integer': 1,
                    }, {
                    'name': 'C',
                    'target': target_c,
                    'integer': 2,
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', 'ilike', '%A%'),
            ('targets.name', 'ilike', '%A'),
            ]
        self.assertEqual(
            Model.search(domain, order=[('integer', 'ASC')]),
            [model_a, model_c])
        self.assertEqual(
            Model.search(domain, order=[('integer', 'DESC')]),
            [model_c, model_a])
        self.assertNotIn(
            'UNION', str(Model.search(
                    domain, order=[('integer', 'ASC')], query=True)))

    @with_transaction()
    def test_search_or_to_union_no_local_clauses(self):
        """
        Test searching for 'OR'-ed domain without local clauses
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union')

        Model.create([{
                    'name': 'A',
                    }, {
                    'name': 'B',
                    }, {
                    'name': 'C',
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('targets.name', 'ilike', '%A'),
            ('targets.name', 'ilike', '%B'),
            ]
        with patch('trytond.model.modelsql.split_subquery_domain') as no_split:
            # Mocking in order not to trigger the split
            no_split.side_effect = lambda d: (d, [])
            result_without_split = Model.search(domain)
            query_without_split = Model.search(domain, query=True)
        self.assertEqual(
            Model.search(domain),
            result_without_split)
        self.assertIn('UNION', str(Model.search(domain, query=True)))
        self.assertNotIn('UNION', str(query_without_split))

    @with_transaction()
    def test_search_or_to_union_class_order(self):
        """
        Test searching for 'OR'-ed domain when the class defines _order
        """
        pool = Pool()
        Model = pool.get('test.modelsql.search.or2union.class_order')
        Target = pool.get('test.modelsql.search.or2union.class_order.target')

        target_a, target_b, target_c = Target.create([
                {'name': 'A'}, {'name': 'B'}, {'name': 'C'},
                ])
        model_a, model_b, model_c = Model.create([{
                    'name': 'A',
                    'reference': str(target_a),
                    }, {
                    'name': 'B',
                    'reference': str(target_b),
                    }, {
                    'name': 'C',
                    'reference': str(target_c),
                    'targets': [('create', [{
                                    'name': 'C.A',
                                    }]),
                        ],
                    }])

        domain = ['OR',
            ('name', 'ilike', '%A%'),
            ('targets.name', 'ilike', '%A'),
            ]
        self.assertEqual(Model.search(domain), [model_c, model_a])
        self.assertIn('UNION', str(Model.search(domain, query=True)))

    @with_transaction()
    def test_search_limit(self):
        "Test searching with limit"
        pool = Pool()
        Model = pool.get('test.modelsql.search')

        Model.create([{'name': str(i)} for i in range(10)])

        self.assertEqual(Model.search([], limit=5, count=True), 5)
        self.assertEqual(Model.search([], limit=20, count=True), 10)
        self.assertEqual(Model.search([], limit=None, count=True), 10)

    @with_transaction()
    def test_search_offset(self):
        "Test searching with offset"
        pool = Pool()
        Model = pool.get('test.modelsql.search')

        Model.create([{'name': str(i)} for i in range(10)])

        self.assertEqual(Model.search([], offset=0, count=True), 10)
        self.assertEqual(Model.search([], offset=5, count=True), 5)
        self.assertEqual(Model.search([], offset=20, count=True), 0)

    def test_split_subquery_domain_empty(self):
        """
        Test the split of domains in local and relation parts (empty domain)
        """
        local, related = split_subquery_domain([])
        self.assertEqual(local, [])
        self.assertEqual(related, [])

    def test_split_subquery_domain_simple(self):
        """
        Test the split of domains in local and relation parts (simple domain)
        """
        local, related = split_subquery_domain([('a', '=', 1)])
        self.assertEqual(local, [('a', '=', 1)])
        self.assertEqual(related, [])

    def test_split_subquery_domain_dotter(self):
        """
        Test the split of domains in local and relation parts (dotted domain)
        """
        local, related = split_subquery_domain([('a.b', '=', 1)])
        self.assertEqual(local, [])
        self.assertEqual(related, [('a.b', '=', 1)])

    def test_split_subquery_domain_mixed(self):
        """
        Test the split of domains in local and relation parts (mixed domains)
        """
        local, related = split_subquery_domain(
            [('a', '=', 1), ('b.c', '=', 2)])
        self.assertEqual(local, [('a', '=', 1)])
        self.assertEqual(related, [('b.c', '=', 2)])

    def test_split_subquery_domain_operator(self):
        """
        Test the split of domains in local and relation parts (with operator)
        """
        local, related = split_subquery_domain(
            ['OR', ('a', '=', 1), ('b.c', '=', 2)])
        self.assertEqual(local, [('a', '=', 1)])
        self.assertEqual(related, [('b.c', '=', 2)])

    def test_split_subquery_domain_nested(self):
        """
        Test the split of domains in local and relation parts (nested domains)
        """
        local, related = split_subquery_domain(
            [
                ['AND', ('a', '=', 1), ('b', '=', 2)],
                ['AND',
                    ('b', '=', 2),
                    ['OR', ('c', '=', 3), ('d.e', '=', 4)]]])
        self.assertEqual(local, [['AND', ('a', '=', 1), ('b', '=', 2)]])
        self.assertEqual(related, [
                ['AND',
                    ('b', '=', 2),
                    ['OR', ('c', '=', 3), ('d.e', '=', 4)]]
                ])


class TranslationTestCase(unittest.TestCase):
    default_language = 'fr'
    other_language = 'en'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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


class ModelSQLTranslationTestCase(TranslationTestCase):
    "Test ModelSQL translation"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('tests')

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
    def test_clear_default_language(self):
        "Test clear default language clear others"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})

        Model.write([record], {'name': ''})

        translations = Translation.search([
                ('name', '=', 'test.modelsql.translation,name'),
                ('res_id', '=', record.id),
                ('type', '=', 'model'),
                ])
        self.assertFalse(translations)

    @with_transaction()
    def test_clear_other_language(self):
        "Test clear other language"
        pool = Pool()
        Model = pool.get('test.modelsql.translation')
        Translation = pool.get('ir.translation')

        record, = Model.create([{'name': "Foo"}])
        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': "Bar"})

        with Transaction().set_context(language=self.other_language):
            Model.write([record], {'name': ''})

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
        self.assertEqual(other.value, "")
        self.assertFalse(other.fuzzy)

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
        # clear transaction cache which may be filled by validation
        other._cache.clear()

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
