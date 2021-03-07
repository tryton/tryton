# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import AccessError
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool

_context = {'_check_access': True}


class _ModelAccessTestCase(unittest.TestCase):
    _perm = None

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    model_name = model_access_name = 'test.access'

    @property
    def model(self):
        pool = Pool()
        Model = pool.get('ir.model')
        model, = Model.search([('model', '=', self.model_access_name)])
        return model

    @property
    def group(self):
        pool = Pool()
        Group = pool.get('res.group')
        group, = Group.search([('users', '=', Transaction().user)])
        return group

    def _assert(self, record):
        raise NotImplementedError

    def _assert_raises(self, record):
        raise NotImplementedError

    @with_transaction(context=_context)
    def test_access_empty(self):
        "Test access without model access"
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])

        self._assert(record)

    @with_transaction(context=_context)
    def test_access_without_group(self):
        "Test access without group"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': None,
                    self._perm: True,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_no_access_without_group(self):
        "Test no access without group"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': None,
                    self._perm: False,
                    }])

        self._assert_raises(record)

    @with_transaction(context=_context)
    def test_one_access_with_groups(self):
        "Test one access with groups"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': None,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_one_access_without_group(self):
        "Test one access without group"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': None,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_all_access_with_groups(self):
        "Test all access with groups"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': None,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_no_access_with_groups(self):
        "Test no access with groups"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': None,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert_raises(record)

    @with_transaction(context=_context)
    def test_one_access_with_group(self):
        "Test one access with group"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_no_access_with_group(self):
        "Test no access with group"
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert_raises(record)

    @with_transaction(context=_context)
    def test_one_access_with_other_group(self):
        "Test one access with other group"
        pool = Pool()
        Group = pool.get('res.group')
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': group.id,
                    self._perm: True,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_no_access_with_other_group(self):
        "Test no access with other group"
        pool = Pool()
        Group = pool.get('res.group')
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': group.id,
                    self._perm: True,
                    }])

        self._assert_raises(record)

    @with_transaction(context=_context)
    def test_one_access_with_other_group_no_perm(self):
        "Test one access with other group no perm"
        pool = Pool()
        Group = pool.get('res.group')
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': group.id,
                    self._perm: False,
                    }])

        self._assert(record)

    @with_transaction(context=_context)
    def test_access_inherited_from_parent(self):
        "Test access inherited from parent"
        pool = Pool()
        Group = pool.get('res.group')
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        Group.write([self.group], {
                'parent': group.id,
                })
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model.id,
                    'group': group.id,
                    self._perm: True,
                    }])

        self._assert(record)


class ModelAccessReadTestCase(_ModelAccessTestCase):
    _perm = 'perm_read'

    def _assert(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        TestAccess.read([record.id], ['field1'])
        TestAccess.search([])

    def _assert_raises(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        with self.assertRaises(AccessError):
            TestAccess.read([record.id], ['field1'])
        with self.assertRaises(AccessError):
            TestAccess.search([])

    @with_transaction(context=_context)
    def test_access_relate_empty(self):
        "Test access on search relate without model access"
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        record, = TestAccess.create([{}])

        TestAccess.read([record.id], ['relate.value'])
        TestAccess.search([('relate.value', '=', 42)])
        TestAccess.search([('reference.value', '=', 42, 'test.access.relate')])

    @with_transaction(context=_context)
    def test_access_relate(self):
        "Test access on search relate"
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        record, = TestAccess.create([{}])
        model, = Model.search([('model', '=', 'test.access.relate')])
        ModelAccess.create([{
                    'model': model.id,
                    'perm_read': True,
                    }])

        TestAccess.read([record.id], ['relate.value'])
        TestAccess.search([('relate.value', '=', 42)])
        TestAccess.search([('reference.value', '=', 42, 'test.access.relate')])
        TestAccess.search([('dict_.key', '=', 42)])
        TestAccess.search([], order=[('relate.value', 'ASC')])
        TestAccess.search([], order=[('dict_.key', 'ASC')])

    @with_transaction(context=_context)
    def test_no_access_relate(self):
        "Test no access on search relate"
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        record, = TestAccess.create([{}])
        model, = Model.search([('model', '=', 'test.access.relate')])
        ModelAccess.create([{
                    'model': model.id,
                    'perm_read': False,
                    }])

        with self.assertRaises(AccessError):
            TestAccess.read([record.id], ['relate.value'])
        with self.assertRaises(AccessError):
            TestAccess.search([('relate.value', '=', 42)])
        with self.assertRaises(AccessError):
            TestAccess.search(
                [('reference.value', '=', 42, 'test.access.relate')])
        with self.assertRaises(AccessError):
            TestAccess.search([], order=[('relate.value', 'ASC')])


class ModelAccessWriteTestCase(_ModelAccessTestCase):
    _perm = 'perm_write'

    def _assert(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        TestAccess.write([record], {})

    def _assert_raises(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        with self.assertRaises(AccessError):
            TestAccess.write([record], {})


class ModelAccessCreateTestCase(_ModelAccessTestCase):
    _perm = 'perm_create'

    def _assert(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        TestAccess.create([{}])

    def _assert_raises(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        with self.assertRaises(AccessError):
            TestAccess.create([{}])


class ModelAccessDeleteTestCase(_ModelAccessTestCase):
    _perm = 'perm_delete'

    def _assert(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        TestAccess.delete([record])

    def _assert_raises(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        with self.assertRaises(AccessError):
            TestAccess.delete([record])


class ModelAccessModelTestCase(_ModelAccessTestCase):
    model_name = 'test.access.model'
    _perm = 'perm_read'

    def _assert(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        TestAccess.read([record.id], ['field1'])
        TestAccess.search([])

    def _assert_raises(self, record):
        pool = Pool()
        TestAccess = pool.get(self.model_name)
        with self.assertRaises(AccessError):
            TestAccess.read([record.id], ['field1'])
        with self.assertRaises(AccessError):
            TestAccess.search([])


class _ModelFieldAccessTestCase(unittest.TestCase):
    _perm = None

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def _field(self, name):
        pool = Pool()
        Field = pool.get('ir.model.field')
        field1, = Field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', name),
                ])
        return field1

    @property
    def field1(self):
        return self._field('field1')

    @property
    def field2(self):
        return self._field('field2')

    @property
    def group(self):
        pool = Pool()
        Group = pool.get('res.group')
        group, = Group.search([('users', '=', Transaction().user)])
        return group

    def _assert1(self, record):
        raise NotImplementedError

    def _assert2(self, record):
        raise NotImplementedError

    def _assert_raises1(self, record):
        raise NotImplementedError

    def _assert_raises2(self, record):
        raise NotImplementedError

    @with_transaction(context=_context)
    def test_access_empty(self):
        "Test access without model field access"
        pool = Pool()
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_access_without_group(self):
        "Test access without group"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_no_access_without_group(self):
        "Test no access without group"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: False,
                    }])

        self._assert_raises1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_one_access_with_groups(self):
        "Test one access with groups"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_one_access_without_group(self):
        "Test one access without group"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_all_access_with_groups(self):
        "Test all access with groups"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_no_access_with_groups(self):
        "Test no access with groups"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert_raises1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_one_access_with_group(self):
        "Test one access with group"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_no_access_with_group(self):
        "Test no access with group"
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert_raises1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_one_access_with_other_group(self):
        "Test no access with other group"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': group.id,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_no_access_with_other_group(self):
        "Test no access with other group"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': group.id,
                    self._perm: True,
                    }])

        self._assert_raises1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_one_access_with_other_group_no_perm(self):
        "Test one access with other group no perm"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': group.id,
                    self._perm: False,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_access_inherited_from_parent(self):
        "Test no access with other group"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        Group.write([self.group], {
                'parent': group.id,
                })
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': group.id,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_two_access(self):
        "Test two access"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': None,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_two_no_access(self):
        "Test two no access"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': None,
                    self._perm: False,
                    }])

        self._assert_raises1(record)
        self._assert_raises2(record)

    @with_transaction(context=_context)
    def test_two_both_access(self):
        "Test two both access"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': None,
                    self._perm: False,
                    }])

        self._assert1(record)
        self._assert_raises2(record)

    @with_transaction(context=_context)
    def test_two_access_with_group(self):
        "Test two access with group"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': None,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_two_access_with_groups(self):
        "Test two access with groups"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])

        self._assert1(record)
        self._assert2(record)

    @with_transaction(context=_context)
    def test_two_no_access_with_group(self):
        "Test two no access with group"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': self.group.id,
                    self._perm: False,
                    }])

        self._assert_raises1(record)
        self._assert_raises2(record)

    @with_transaction(context=_context)
    def test_two_both_access_with_group(self):
        "Test two both access with group"
        pool = Pool()
        Group = pool.get('res.group')
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        record, = TestAccess.create([{}])
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.create([{
                    'field': self.field1.id,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'field': self.field2.id,
                    'group': None,
                    self._perm: False,
                    }])

        self._assert1(record)
        self._assert_raises2(record)


class ModelFieldAccessReadTestCase(_ModelFieldAccessTestCase):
    _perm = 'perm_read'

    def _assert1(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        TestAccess.read([record.id], ['field1'])
        TestAccess.search([('field1', '=', 'test')])

    def _assert2(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        TestAccess.read([record.id], ['field2'])
        TestAccess.search([('field2', '=', 'test')])

    def _assert_raises1(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        with self.assertRaises(AccessError):
            TestAccess.read([record.id], ['field1'])
        with self.assertRaises(AccessError):
            TestAccess.search([('field1', '=', 'test')])

    def _assert_raises2(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        with self.assertRaises(AccessError):
            TestAccess.read([record.id], ['field2'])
        with self.assertRaises(AccessError):
            TestAccess.search([('field2', '=', 'test')])

    @with_transaction(context=_context)
    def test_access_search_relate_empty(self):
        "Test access on search relate"
        pool = Pool()
        TestAccess = pool.get('test.access')

        TestAccess.search([('relate.value', '=', 42)])
        TestAccess.search([('reference.value', '=', 42, 'test.access.relate')])

    @with_transaction(context=_context)
    def test_access_search_relate(self):
        "Test access on search relate"
        pool = Pool()
        TestAccess = pool.get('test.access')
        Field = pool.get('ir.model.field')
        FieldAccess = pool.get('ir.model.field.access')
        field, = Field.search([
                ('model.model', '=', 'test.access.relate'),
                ('name', '=', 'value'),
                ])
        FieldAccess.create([{
                    'field': field.id,
                    'perm_read': True,
                    }])

        TestAccess.search([('relate.value', '=', 42)])
        TestAccess.search([('reference.value', '=', 42, 'test.access.relate')])
        TestAccess.search([], order=[('relate.value', 'ASC')])

    @with_transaction(context=_context)
    def test_no_access_search_relate(self):
        "Test access on search relate"
        pool = Pool()
        TestAccess = pool.get('test.access')
        Field = pool.get('ir.model.field')
        FieldAccess = pool.get('ir.model.field.access')
        field, = Field.search([
                ('model.model', '=', 'test.access.relate'),
                ('name', '=', 'value'),
                ])
        FieldAccess.create([{
                    'field': field.id,
                    'perm_read': False,
                    }])

        with self.assertRaises(AccessError):
            TestAccess.search([('relate.value', '=', 42)])
        with self.assertRaises(AccessError):
            TestAccess.search(
                [('reference.value', '=', 42, 'test.access.relate')])
        with self.assertRaises(AccessError):
            TestAccess.search([], order=[('relate.value', 'ASC')])


class ModelFieldAccessWriteTestCase(_ModelFieldAccessTestCase):
    _perm = 'perm_write'

    def _assert1(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        TestAccess.write([record], {'field1': 'test'})

    def _assert2(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        TestAccess.write([record], {'field2': 'test'})

    def _assert_raises1(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        with self.assertRaises(AccessError):
            TestAccess.write([record], {'field1': 'test'})

    def _assert_raises2(self, record):
        pool = Pool()
        TestAccess = pool.get('test.access')
        with self.assertRaises(AccessError):
            TestAccess.write([record], {'field2': 'test'})


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessReadTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessWriteTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessCreateTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessDeleteTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessModelTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelFieldAccessReadTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelFieldAccessWriteTestCase))
    return suite_
