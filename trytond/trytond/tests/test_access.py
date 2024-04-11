# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction

_context = {'_check_access': True}


class _ModelAccessTestCase(unittest.TestCase):
    _perm = None

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    model_name = model_access_name = 'test.access'

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
                    'model': self.model_name,
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
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': None,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': None,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': None,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': None,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
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
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': self.group.id,
                    self._perm: True,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
                    'model': self.model_name,
                    'group': self.group.id,
                    self._perm: False,
                    }])
        ModelAccess.create([{
                    'model': self.model_name,
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
        ModelAccess = pool.get('ir.model.access')
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': 'test.access.relate',
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
        ModelAccess = pool.get('ir.model.access')
        record, = TestAccess.create([{}])
        ModelAccess.create([{
                    'model': 'test.access.relate',
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
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field1',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': None,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: False,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
                    'model': 'test.access',
                    'field': 'field1',
                    'group': self.group.id,
                    self._perm: True,
                    }])
        FieldAccess.create([{
                    'model': 'test.access',
                    'field': 'field2',
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
        FieldAccess = pool.get('ir.model.field.access')
        FieldAccess.create([{
                    'model': 'test.access.relate',
                    'field': 'value',
                    'perm_read': True,
                    }])

        TestAccess.search([('relate.value', '=', 42)])
        TestAccess.search([('reference.value', '=', 42, 'test.access.relate')])
        TestAccess.search([
                ('reference.parent.value', '=', 42, 'test.access.relate')])
        TestAccess.search([], order=[('relate.value', 'ASC')])

    @with_transaction(context=_context)
    def test_no_access_search_relate(self):
        "Test access on search relate"
        pool = Pool()
        TestAccess = pool.get('test.access')
        FieldAccess = pool.get('ir.model.field.access')
        FieldAccess.create([{
                    'model': 'test.access.relate',
                    'field': 'value',
                    'perm_read': False,
                    }])

        with self.assertRaises(AccessError):
            TestAccess.search([('relate.value', '=', 42)])
        with self.assertRaises(AccessError):
            TestAccess.search(
                [('reference.value', '=', 42, 'test.access.relate')])
        with self.assertRaises(AccessError):
            TestAccess.search(
                [('reference.parent.value', '=', 42, 'test.access.relate')])
        with self.assertRaises(AccessError):
            TestAccess.search([], order=[('relate.value', 'ASC')])

    @with_transaction(context=_context)
    def test_access_search_relate_parent_field(self):
        "Test access on search relate with a parent field"
        pool = Pool()
        TestAccess = pool.get('test.access')
        FieldAccess = pool.get('ir.model.field.access')
        FieldAccess.create([{
                    'model': 'test.access.relate',
                    'field': 'parent',
                    'perm_read': True,
                    }])

        TestAccess.search([('relate', 'child_of', 42, 'parent')])

    @with_transaction(context=_context)
    def test_no_access_search_relate_parent_field(self):
        "Test no access on search relate with a parent field"
        pool = Pool()
        TestAccess = pool.get('test.access')
        FieldAccess = pool.get('ir.model.field.access')
        FieldAccess.create([{
                    'model': 'test.access.relate',
                    'field': 'parent',
                    'perm_read': False,
                    }])

        with self.assertRaises(AccessError):
            TestAccess.search([('relate', 'child_of', 42, 'parent')])


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


class MenuActionAccessReadTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    def create_menu(self, access=None):
        pool = Pool()
        Action = pool.get('ir.action.act_window')
        Menu = pool.get('ir.ui.menu')
        ModelAccess = pool.get('ir.model.access')

        action = Action(name="Test", res_model='test.access')
        action.save()
        menu = Menu(name="Test", action=action)
        menu.save()

        if access is not None:
            ModelAccess.create([{
                        'model': 'test.access',
                        'perm_read': access,
                        }])
        return menu

    @with_transaction(context=_context)
    def test_access_empty(self):
        "Search menu without model access"
        pool = Pool()
        Menu = pool.get('ir.ui.menu')

        menu = self.create_menu()

        self.assertEqual(Menu.search([('id', '=', menu.id)]), [menu])

    @with_transaction(context=_context)
    def test_access(self):
        "Search menu with model access"
        pool = Pool()
        Menu = pool.get('ir.ui.menu')

        menu = self.create_menu(True)

        self.assertEqual(Menu.search([('id', '=', menu.id)]), [menu])

    @with_transaction(context=_context)
    def test_no_access(self):
        "Search menu with no model access"
        pool = Pool()
        Menu = pool.get('ir.ui.menu')

        menu = self.create_menu(False)

        self.assertEqual(Menu.search([('id', '=', menu.id)]), [])


del _ModelAccessTestCase, _ModelFieldAccessTestCase
