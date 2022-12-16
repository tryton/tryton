# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest
import time
from unittest.mock import patch, call

from trytond import backend
from trytond.exceptions import UserError, ConcurrencyException
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class ModelSQLTestCase(unittest.TestCase):
    'Test ModelSQL'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @unittest.skipIf(backend.name() == 'sqlite',
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
            except UserError as err:
                # message must not quote key
                msg = "'%s' not missing but quoted in error: '%s'" % (key,
                        err.message)
                self.assertTrue(key not in err.message, msg)
            else:
                self.fail('UserError should be caught')
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

        if backend.name() == 'sqlite':
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
        record = ParentModel(name="test")
        record.targets = [TargetModel()]
        with self.assertRaises(UserError) as cm:
            record.save()
        err = cm.exception
        msg = 'The field "%s" on "%s" is required.' % (
            TargetModel.name.string, TargetModel.__doc__)
        self.assertEqual(err.message, msg)

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

        with self.assertRaises(UserError):
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

        with self.assertRaises(UserError):
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

        with self.assertRaises(UserError):
            Model.create([{'value': 42}, {'value': 42}])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ModelSQLTestCase)
