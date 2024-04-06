# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest

from trytond.model import EvalEnvironment
from trytond.model.exceptions import (
    AccessError, DomainValidationError, RequiredValidationError)
from trytond.model.modelstorage import _UnsavedRecordError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction, check_access


class ModelStorageTestCase(unittest.TestCase):
    'Test ModelStorage'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_search_read_order(self):
        'Test search_read order'
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')

        ModelStorage.create([{'name': i} for i in ['foo', 'bar', 'test']])

        rows = ModelStorage.search_read([])
        self.assertTrue(
            all(x['id'] < y['id'] for x, y in zip(rows, rows[1:])))

        rows = ModelStorage.search_read(
            [], order=[('name', 'ASC')], fields_names=['name'])
        self.assertTrue(
            all(x['name'] <= y['name'] for x, y in zip(rows, rows[1:])))

        rows = ModelStorage.search_read(
            [], order=[('name', 'DESC')], fields_names=['name'])
        self.assertTrue(
            all(x['name'] >= y['name'] for x, y in zip(rows, rows[1:])))

    @with_transaction()
    def test_copy_order(self):
        "Test copy order"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')

        # Use both order to avoid false positive by chance
        records = ModelStorage.create(
            [{'name': n} for n in ['foo', 'bar', 'test']])
        new_records = ModelStorage.copy(records)
        reversed_records = list(reversed(records))
        new_reversed_records = ModelStorage.copy(reversed_records)

        self.assertListEqual(
            [r.name for r in records],
            [r.name for r in new_records])
        self.assertListEqual(
            [r.name for r in reversed_records],
            [r.name for r in new_reversed_records])

    @with_transaction()
    def test_search_count(self):
        "Test search_count"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')
        ModelStorage.create([{'name': 'Test %s' % i} for i in range(10)])

        count = ModelStorage.search_count([])
        self.assertEqual(count, 10)

        count = ModelStorage.search_count([('name', '=', 'Test 5')])
        self.assertEqual(count, 1)

    @with_transaction()
    def test_browse_deleted(self):
        "Test access record from browse list with deleted record"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage')
        records = ModelStorage.create(
            [{'name': 'Test %s' % i} for i in range(2)])

        ModelStorage.delete(records[1:])
        ModelStorage.write(records[:1], {})  # clean cache

        records[0].name
        with self.assertRaises(AccessError):
            records[1].name

    @with_transaction()
    def test_browse_context(self):
        'Test context when browsing'
        pool = Pool()
        ModelStorageContext = pool.get('test.modelstorage.context')

        record, = ModelStorageContext.create([{}])
        record_context = {'_check_access': False}  # From Function.get

        self.assertDictEqual(record.context, record_context)

        # Clean the instance cache
        record = ModelStorageContext(record.id)

        with Transaction().set_context(foo='bar'):
            self.assertDictEqual(record.context, record_context)

            record = ModelStorageContext(record.id)
            self.assertEqual(record.context.get('foo'), 'bar')

    @with_transaction()
    def test_save_mixed_context(self):
        'Test save with mixed context '
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.required')

        foo = ModelStorage(name='foo')
        with Transaction().set_context(bar=True):
            bar = ModelStorage(name='bar')
        ModelStorage.save([foo, bar])

        self.assertNotEqual(foo._context, bar._context)

    @with_transaction()
    def test_fail_saving_mixed_context1(self):
        'Test fail saving with mixed context '
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.required')

        foo = ModelStorage(name='foo')
        with Transaction().set_context(bar=True):
            bar = ModelStorage(name='bar')
        ModelStorage.save([foo, bar])
        foo.name = None
        with self.assertRaises(RequiredValidationError):
            ModelStorage.save([foo, bar])

    @with_transaction()
    def test_fail_saving_mixed_context2(self):
        'Test fail saving with mixed context '
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.required')

        foo = ModelStorage(name='foo')
        with Transaction().set_context(bar=True):
            bar = ModelStorage(name='bar')
        ModelStorage.save([foo, bar])

        bar.name = None
        foo.name = 'foo'
        with self.assertRaises(RequiredValidationError):
            ModelStorage.save([foo, bar])

    @with_transaction()
    def test_many2one_save_raise_exception(self):
        "Test _save_values raises _UnsavedRecordError on unsaved record"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save_m2o')
        Target = pool.get('test.modelstorage.save_m2o.target')

        record = ModelStorage()
        record.target = target = Target()

        with self.assertRaises(_UnsavedRecordError) as cm:
            record._save_values

        self.assertEqual(cm.exception.record, target)

    @with_transaction()
    def test_save_many2one_create(self):
        "Test saving a record while creating a Many2One"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save_m2o')
        Target = pool.get('test.modelstorage.save_m2o.target')

        record = ModelStorage()
        record.target = target = Target()
        with self.assertWarnsRegex(
                UserWarning, r"Using an unsaved relation record:"):
            record.save()

        self.assertIsNotNone(record.id)
        self.assertIsNotNone(target.id)

    @with_transaction()
    def test_save_many2one_create_multi(self):
        "Test saving multiple records while creating a M2O"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save_m2o')
        Target = pool.get('test.modelstorage.save_m2o.target')

        record1 = ModelStorage()
        record1.target = target = Target()
        record1.save()

        record2 = ModelStorage()
        record2.target = target
        record2.save()

        ModelStorage.save([record1, record2])

        self.assertIsNotNone(record1.id)
        self.assertIsNotNone(record2.id)
        self.assertEqual(record1.target.id, record2.target.id)
        self.assertNotEqual(record2.id, record1.id)

    @with_transaction()
    def test_save_many2one_in_one2many_create(self):
        "Test saving a record while creating a M2O contained in a O2M"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save_m2o')
        Target = pool.get('test.modelstorage.save_m2o.target')
        M2OTarget = pool.get('test.modelstorage.save_m2o.o2m_target.target')

        target = Target()
        target.target = m2o_target = M2OTarget()
        record = ModelStorage()
        record.targets = [target]
        record.save()

        self.assertIsNotNone(record.id)
        self.assertIsNotNone(m2o_target.id)
        self.assertEqual(len(record.targets), 1)
        self.assertEqual(record.targets[0].target, m2o_target)

    @with_transaction()
    def test_save_one2many_create(self):
        "Test save one2many create"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        record = ModelStorage()
        record.targets = [Target()]
        record.save()

        self.assertTrue(record.id)
        self.assertEqual(len(record.targets), 1)

    @with_transaction()
    def test_save_one2many_add(self):
        "Test save one2many add"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        target = Target()
        target.save()
        record = ModelStorage()
        record.targets = [target]
        record.save()

        self.assertTrue(record.id)
        self.assertEqual(len(record.targets), 1)
        self.assertEqual(len(Target.search([])), 1)

    @with_transaction()
    def test_save_one2many_delete(self):
        "Test save one2many delete"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        record, = ModelStorage.create([{'targets': [('create', [{}])]}])
        record.targets = []
        record.save()

        self.assertEqual(len(record.targets), 0)
        self.assertEqual(Target.search([], count=True), 0)

    @with_transaction()
    def test_save_one2many_remove(self):
        "Test save one2many remove"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        record, = ModelStorage.create([{'targets': [('create', [{}])]}])
        ModelStorage.targets.remove(record, record.targets)
        record.save()

        self.assertEqual(len(record.targets), 0)
        self.assertEqual(Target.search([], count=True), 1)

    @with_transaction()
    def test_save_many2many_add(self):
        "Test save many2many add"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        target = Target()
        target.save()
        record = ModelStorage()
        record.m2m_targets = [target]
        record.save()

        self.assertTrue(record.id)
        self.assertEqual(len(record.m2m_targets), 1)
        self.assertEqual(len(Target.search([])), 1)

    @with_transaction()
    def test_save_many2many_delete(self):
        "Test save many2many delete"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        record, = ModelStorage.create([{'m2m_targets': [('create', [{}])]}])
        ModelStorage.m2m_targets.delete(record, record.m2m_targets)
        record.save()

        self.assertEqual(len(record.targets), 0)
        self.assertEqual(Target.search([], count=True), 0)

    @with_transaction()
    def test_save_many2many_remove(self):
        "Test save one2many remove"
        pool = Pool()
        ModelStorage = pool.get('test.modelstorage.save2many')
        Target = pool.get('test.modelstorage.save2many.target')

        target = Target()
        target.save()
        record, = ModelStorage.create([
                {'m2m_targets': [('add', [target.id])]}])
        record.m2m_targets = []
        record.save()

        self.assertEqual(len(record.m2m_targets), 0)
        self.assertEqual(Target.search([], count=True), 1)

    @with_transaction(context={'_check_access': True})
    def test_model_translations(self):
        'Test any user can translate fields and duplicate its records'
        pool = Pool()
        Transalatable = pool.get('test.char_translate')
        Lang = pool.get('ir.lang')
        User = pool.get('res.user')
        lang, = Lang.search([
                ('translatable', '=', False),
                ('code', '!=', 'en'),
                ], limit=1)
        lang.translatable = True
        lang.save()

        user = User(login='test')
        user.save()
        with Transaction().set_user(user.id):
            record = Transalatable(char='foo')
            record.save()
            with Transaction().set_context(lang=lang.code):
                record = Transalatable(record.id)
                record.char = 'bar'
                record.save()
                # Test we can copy and translations are copied
                copied_record, = Transalatable.copy([record])
                copied_record = Transalatable(copied_record.id)
                self.assertEqual(copied_record.char, 'bar')

    @with_transaction()
    def test_pyson_domain_same(self):
        "Test same pyson domain validation"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        Model.create([{'constraint': 'foo', 'value': 'foo'}] * 10)

        with self.assertRaises(DomainValidationError) as cm:
            Model.create([{'constraint': 'foo', 'value': 'bar'}] * 10)
        self.assertEqual(cm.exception.domain[0], [['value', '=', 'foo']])
        self.assertTrue(cm.exception.domain[1]['value'])

    @with_transaction()
    def test_pyson_domain_unique(self):
        "Test unique pyson domain validation"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        Model.create(
            [{'constraint': str(i), 'value': str(i)} for i in range(10)])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create(
                [{'constraint': str(i), 'value': str(i + 1)}
                    for i in range(10)])
        self.assertTrue(cm.exception.domain[0])
        self.assertTrue(cm.exception.domain[1]['value'])

    @with_transaction()
    def test_pyson_domain_unique_in_max(self):
        "Test unique pyson domain validation with greater IN_MAX"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        in_max = Transaction().database.IN_MAX
        self.addCleanup(setattr, Transaction().database, 'IN_MAX', in_max)
        Transaction().database.IN_MAX = 1

        # Use modulo 6 so len(domains) is greater then len(records) * 0.5
        # and more than 1 (IN_MAX) have the same domain
        Model.create(
            [{'constraint': str(i % 6), 'value': str(i % 6)}
                for i in range(10)])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create(
                [{'constraint': str(i % 6), 'value': str(i)}
                    for i in range(10)])
        self.assertTrue(cm.exception.domain[0])
        self.assertTrue(cm.exception.domain[1]['value'])

    @with_transaction()
    def test_pyson_domain_single(self):
        "Test pyson domain validation for 1 record"
        pool = Pool()
        Model = pool.get('test.modelstorage.pyson_domain')

        Model.create([{'constraint': 'foo', 'value': 'foo'}])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create([{'constraint': 'foo', 'value': 'bar'}])
        self.assertEqual(cm.exception.domain[0], [['value', '=', 'foo']])
        self.assertTrue(cm.exception.domain[1]['value'])

    @with_transaction()
    def test_relation_domain(self):
        "Test valid relation domain"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{'value': 'valid'}])

        record, = Model.create([{'relation': target.id}])

    @with_transaction()
    def test_relation_domain_invalid(self):
        "Test invalid relation domain"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{'value': 'invalid'}])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create([{'relation': target.id}])
        self.assertEqual(cm.exception.domain[0], [('value', '=', 'valid')])
        self.assertTrue(cm.exception.domain[1]['value'])

    @with_transaction()
    def test_relation_domain_multi(self):
        "Test relation multi domain"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_multi_domain')
        Target = pool.get('test.modelstorage.relation_multi_domain.target')

        target, = Target.create([{'test1': True, 'test2': True}])

        record, = Model.create([{'relation': target.id}])

    @with_transaction()
    def test_relation_domain_multi_invalid(self):
        "Test invalid relation multi domain"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_multi_domain')
        Target = pool.get('test.modelstorage.relation_multi_domain.target')

        target1, target2 = Target.create(
            [{'test1': False, 'test2': True}, {'test1': True, 'test2': False}])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create([{
                        'relation': target1.id,
                        }])
        self.assertEqual(cm.exception.domain[0], [('test1', '=', True)])
        self.assertEqual(cm.exception.domain[1].keys(), {'test1'})

        with self.assertRaises(DomainValidationError) as cm:
            Model.create([{
                        'relation': target2.id,
                        }])
        self.assertEqual(cm.exception.domain[0], [('test2', '=', True)])
        self.assertEqual(cm.exception.domain[1].keys(), {'test2'})

    @with_transaction()
    def test_relation_pyson_domain(self):
        "Test valid relation with PYSON"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{'value': 'valid'}])

        record, = Model.create(
            [{'relation_pyson': target.id, 'relation_valid': True}])

    @with_transaction()
    def test_relation_pyson_domain_invalid(self):
        "Test valid relation with PYSON"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{'value': 'valid'}])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create(
                [{'relation_pyson': target.id, 'relation_valid': False}])
        self.assertEqual(cm.exception.domain[0], [['value', '!=', 'valid']])
        self.assertTrue(cm.exception.domain[1], 'value')

    @with_transaction()
    def test_relation_domain_context(self):
        "Test valid relation with context"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{}])

        record, = Model.create(
            [{'relation_context': target.id, 'relation_valid': True}])

    @with_transaction()
    def test_relation_domain_context_invalid(self):
        "Test invalid relation with context"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{}])

        with self.assertRaises(DomainValidationError):
            record, = Model.create(
                [{'relation_context': target.id, 'relation_valid': False}])

    @with_transaction()
    def test_relation_pyson_domain_context(self):
        "Test valid relation with PYSON and context"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{}])

        record, = Model.create(
            [{'relation_pyson_context': target.id, 'relation_valid': True}])

    @with_transaction()
    def test_relation_pyson_domain_context_invalid(self):
        "Test invalid relation with PYSON and context"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{}])

        with self.assertRaises(DomainValidationError):
            record, = Model.create([{
                        'relation_pyson_context': target.id,
                        'relation_valid': False}])

    @with_transaction()
    def test_relation2_domain_invalid(self):
        "Test invalid relation domain with 2 level"
        pool = Pool()
        Model = pool.get('test.modelstorage.relation_domain2')
        Target2 = pool.get('test.modelstorage.relation_domain2.target')
        Target = pool.get('test.modelstorage.relation_domain.target')

        target, = Target.create([{'value': 'invalid'}])
        target2, = Target2.create([{'relation2': target.id}])

        with self.assertRaises(DomainValidationError) as cm:
            Model.create([{'relation': target2.id}])
        self.assertEqual(
            cm.exception.domain[0], [('relation2.value', '=', 'valid')])
        self.assertTrue(cm.exception.domain[1]['relation2'])
        self.assertTrue(
            cm.exception.domain[1]['relation2']['relation_fields']['value'])

    @with_transaction()
    def test_domain_not_required_validation(self):
        "Test domain validation on not required"
        pool = Pool()
        Model = pool.get('test.modelstorage.domain_not_required')
        Model.create([{'domain_not_required': None}])

    @with_transaction()
    def test_domain_not_required_invalid(self):
        "Test invalid domain on not required"
        pool = Pool()
        Model = pool.get('test.modelstorage.domain_not_required')

        with self.assertRaises(DomainValidationError):
            Model.create([{'domain_not_required': 0}])

    @with_transaction()
    def test_check_xml_record_without_record(self):
        "Test check_xml_record without record"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        record, = Model.create([{}])

        Model.check_xml_record([record], {'name': "Test"})

    @with_transaction()
    def test_check_xml_record_with_record_no_matching_values(self):
        "Test check_xml_record with record and no matching values"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{}])
        ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': ModelData.dump_values({}),
                    'noupdate': False,
                    }])

        Model.check_xml_record([record], {'name': "Test"})

    @with_transaction()
    def test_check_xml_record_with_record_matching_values(self):
        "Test check_xml_record with record and matching values"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': ModelData.dump_values({'name': "Foo"}),
                    'noupdate': False,
                    }])

        with self.assertRaises(AccessError):
            Model.check_xml_record([record], {'name': "Bar"})

    @with_transaction()
    def test_check_xml_record_with_record_matching_values_noupdate(self):
        "Test check_xml_record with record and matching values but noupdate"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': ModelData.dump_values({'name': "Foo"}),
                    'noupdate': True,
                    }])

        Model.check_xml_record([record], {'name': "Bar"})

    @with_transaction(user=0)
    def test_check_xml_record_with_record_matching_values_root(self):
        "Test check_xml_record with record with matching values as root"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': ModelData.dump_values({'name': "Foo"}),
                    'noupdate': False,
                    }])

        Model.check_xml_record([record], {'name': "Bar"})

    @with_transaction()
    def test_check_xml_record_with_record_no_values(self):
        "Test check_xml_record with record and no values"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': None,
                    'noupdate': False,
                    }])

        with self.assertRaises(AccessError):
            Model.check_xml_record([record], None)

    @with_transaction()
    def test_check_xml_record_with_record_no_values_noupdate(self):
        "Test check_xml_record with record and no values but noupdate"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': None,
                    'noupdate': True,
                    }])

        Model.check_xml_record([record], None)

    @with_transaction()
    def test_delete_clear_db_id_model_data_noupdate(self):
        "Test delete record clear DB id from model data"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        data, = ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': None,
                    'noupdate': True,
                    }])

        Model.delete([record])

        self.assertIsNone(data.db_id)

    @with_transaction(user=0)
    def test_delete_model_data_without_noupdate(self):
        "Test delete record from model data without noupdate"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        ModelData = pool.get('ir.model.data')
        record, = Model.create([{'name': "Foo"}])
        data, = ModelData.create([{
                    'fs_id': 'test',
                    'model': 'test.modelstorage',
                    'module': 'tests',
                    'db_id': record.id,
                    'values': None,
                    'noupdate': False,
                    }])

        Model.delete([record])


class EvalEnvironmentTestCase(unittest.TestCase):
    "Test EvalEnvironment"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_char_field(self):
        "Test eval simple field"
        pool = Pool()
        Model = pool.get('test.modelstorage.eval_environment')

        record = Model(char="Test")
        env = EvalEnvironment(record, Model)

        self.assertEqual(env.get('char'), "Test")

    @with_transaction()
    def test_reference_field(self):
        "Test eval reference field"
        pool = Pool()
        Model = pool.get('test.modelstorage.eval_environment')

        record = Model(reference=Model(id=1))
        env = EvalEnvironment(record, Model)

        self.assertEqual(
            env.get('reference'), 'test.modelstorage.eval_environment,1')

    @with_transaction()
    def test_many2one_field(self):
        "Test eval many2one field"
        pool = Pool()
        Model = pool.get('test.modelstorage.eval_environment')

        record = Model(many2one=Model(id=1))
        env = EvalEnvironment(record, Model)

        self.assertEqual(env.get('many2one'), 1)

    @with_transaction()
    def test_one2many_field(self):
        "Test eval one2many field"
        pool = Pool()
        Model = pool.get('test.modelstorage.eval_environment')

        record = Model(one2many=[Model(id=1), Model(id=2)])
        env = EvalEnvironment(record, Model)

        self.assertEqual(env.get('one2many'), [1, 2])

    @with_transaction()
    def test_multiselection_field(self):
        "Test eval multiselection field"
        pool = Pool()
        Model = pool.get('test.modelstorage.eval_environment')

        record = Model(multiselection=['value1', 'value2'])
        env = EvalEnvironment(record, Model)

        self.assertEqual(env.get('multiselection'), ('value1', 'value2'))

    @with_transaction()
    def test_parent_field(self):
        "Test eval parent field"
        pool = Pool()
        Model = pool.get('test.modelstorage.eval_environment')

        record = Model(many2one=Model(char="Test"))
        env = EvalEnvironment(record, Model)

        self.assertEqual(env.get('_parent_many2one').get('char'), "Test")

    @with_transaction()
    def test_model_save_skip_check_access(self):
        "Test model save skips check access"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        IrModelAccess = pool.get('ir.model.access')

        IrModelAccess.create([{
                    'model': Model.__name__,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': False,
                    }])
        with check_access():
            record = Model(name="Test")
            record.save()

    @with_transaction()
    def test_model_getattr_skip_check_access(self):
        "Test model getattr skips check access"
        pool = Pool()
        Model = pool.get('test.modelstorage')
        IrModelAccess = pool.get('ir.model.access')

        IrModelAccess.create([{
                    'model': Model.__name__,
                    'perm_read': False,
                    'perm_create': False,
                    'perm_write': False,
                    'perm_delete': False,
                    }])
        record, = Model.create([{'name': "Test"}])

        with check_access():
            record = Model(record.id)

            self.assertEqual(record.name, "Test")
