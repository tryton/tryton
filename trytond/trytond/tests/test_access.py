#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction


class ModelAccessTestCase(unittest.TestCase):
    '''
    Test Model Access
    '''

    def setUp(self):
        install_module('test')
        self.model_access = POOL.get('ir.model.access')
        self.test_access = POOL.get('test.access')
        self.model = POOL.get('ir.model')
        self.group = POOL.get('res.group')

    def test0010perm_read(self):
        '''
        Test Read Access
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id, = self.model.search([('model', '=', 'test.access')])

            test_id = self.test_access.create({})

            # Without model access
            self.test_access.read(test_id)

            # With model access

            # One access allowed for any group
            model_access_wo_group_id = self.model_access.create({
                'model': model_id,
                'group': False,
                'perm_read': True,
                })
            self.test_access.read(test_id)

            # One access disallowed for any group
            self.model_access.write(model_access_wo_group_id, {
                'perm_read': False,
                })
            self.failUnlessRaises(Exception, self.test_access.read,
                    test_id)

            # Two access rules with one group allowed
            group_id = self.group.search([('users', '=', USER)])[0]
            model_access_w_group_id = self.model_access.create({
                'model': model_id,
                'group': group_id,
                'perm_read': True,
                })

            self.test_access.read(test_id)

            # Two access rules with both allowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_read': True,
                })
            self.test_access.read(test_id)

            # Two access rules with any group allowed
            self.model_access.write(model_access_w_group_id, {
                'perm_read': False,
                })
            self.test_access.read(test_id)

            # Two access rules with both disallowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_read': False,
                })
            self.failUnlessRaises(Exception, self.test_access.read,
                    test_id)

            # One access disallowed for one group
            self.model_access.delete(model_access_wo_group_id)
            self.failUnlessRaises(Exception, self.test_access.read,
                    test_id)

            # One access allowed for one group
            self.model_access.write(model_access_w_group_id, {
                'perm_read': True,
                })
            self.test_access.read(test_id)

            # One access allowed for one other group
            group_id = self.group.create({'name': 'Test'})
            self.model_access.write(model_access_w_group_id, {
                'group': group_id,
                })
            self.test_access.read(test_id)

            # One access disallowed for one other group
            self.model_access.write(model_access_w_group_id, {
                'perm_read': False,
                })
            self.test_access.read(test_id)

            transaction.cursor.rollback()

    def test0020perm_write(self):
        '''
        Test Write Access
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id, = self.model.search([('model', '=', 'test.access')])

            test_id = self.test_access.create({})

            # Without model access
            self.test_access.write(test_id, {})

            # With model access

            # One access allowed for any group
            model_access_wo_group_id = self.model_access.create({
                'model': model_id,
                'group': False,
                'perm_write': True,
                })
            self.test_access.write(test_id, {})

            # One access disallowed for any group
            self.model_access.write(model_access_wo_group_id, {
                'perm_write': False,
                })
            self.failUnlessRaises(Exception, self.test_access.write,
                    test_id, {})

            # Two access rules with one group allowed
            group_id = self.group.search([('users', '=', USER)])[0]
            model_access_w_group_id = self.model_access.create({
                'model': model_id,
                'group': group_id,
                'perm_write': True,
                })

            self.test_access.write(test_id, {})

            # Two access rules with both allowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_write': True,
                })
            self.test_access.write(test_id, {})

            # Two access rules with any group allowed
            self.model_access.write(model_access_w_group_id, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})

            # Two access rules with both disallowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_write': False,
                })
            self.failUnlessRaises(Exception, self.test_access.write,
                    test_id, {})

            # One access disallowed for one group
            self.model_access.delete(model_access_wo_group_id)
            self.failUnlessRaises(Exception, self.test_access.write,
                    test_id, {})

            # One access allowed for one group
            self.model_access.write(model_access_w_group_id, {
                'perm_write': True,
                })
            self.test_access.write(test_id, {})

            # One access allowed for one other group
            group_id = self.group.create({'name': 'Test'})
            self.model_access.write(model_access_w_group_id, {
                'group': group_id,
                })
            self.test_access.write(test_id, {})

            # One access disallowed for one other group
            self.model_access.write(model_access_w_group_id, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})

            transaction.cursor.rollback()

    def test0030perm_create(self):
        '''
        Test Create Access
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id, = self.model.search([('model', '=', 'test.access')])

            # Without model access
            test_id = self.test_access.create({})

            # With model access

            # One access allowed for any group
            model_access_wo_group_id = self.model_access.create({
                'model': model_id,
                'group': False,
                'perm_create': True,
                })
            self.test_access.create({})

            # One access disallowed for any group
            self.model_access.write(model_access_wo_group_id, {
                'perm_create': False,
                })
            self.failUnlessRaises(Exception, self.test_access.create, {})

            # Two access rules with one group allowed
            group_id = self.group.search([('users', '=', USER)])[0]
            model_access_w_group_id = self.model_access.create({
                'model': model_id,
                'group': group_id,
                'perm_create': True,
                })

            self.test_access.create({})

            # Two access rules with both allowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_create': True,
                })
            self.test_access.create({})

            # Two access rules with any group allowed
            self.model_access.write(model_access_w_group_id, {
                'perm_create': False,
                })
            self.test_access.create({})

            # Two access rules with both disallowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_create': False,
                })
            self.failUnlessRaises(Exception, self.test_access.create, {})

            # One access disallowed for one group
            self.model_access.delete(model_access_wo_group_id)
            self.failUnlessRaises(Exception, self.test_access.create, {})

            # One access allowed for one group
            self.model_access.write(model_access_w_group_id, {
                'perm_create': True,
                })
            self.test_access.create({})

            # One access allowed for one other group
            group_id = self.group.create({'name': 'Test'})
            self.model_access.write(model_access_w_group_id, {
                'group': group_id,
                })
            self.test_access.create({})

            # One access disallowed for one other group
            self.model_access.write(model_access_w_group_id, {
                'perm_create': False,
                })
            self.test_access.create({})

            transaction.cursor.rollback()

    def test0040perm_delete(self):
        '''
        Test Delete Access
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model_id, = self.model.search([('model', '=', 'test.access')])

            test_ids = [self.test_access.create({}) for x in range(11)]

            # Without model access
            test_id = self.test_access.delete(test_ids.pop())

            # With model access

            # One access allowed for any group
            model_access_wo_group_id = self.model_access.create({
                'model': model_id,
                'group': False,
                'perm_delete': True,
                })
            self.test_access.delete(test_ids.pop())

            # One access disallowed for any group
            self.model_access.write(model_access_wo_group_id, {
                'perm_delete': False,
                })
            self.failUnlessRaises(Exception, self.test_access.delete,
                    test_ids.pop())

            # Two access rules with one group allowed
            group_id = self.group.search([('users', '=', USER)])[0]
            model_access_w_group_id = self.model_access.create({
                'model': model_id,
                'group': group_id,
                'perm_delete': True,
                })

            self.test_access.delete(test_ids.pop())

            # Two access rules with both allowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_delete': True,
                })
            self.test_access.delete(test_ids.pop())

            # Two access rules with any group allowed
            self.model_access.write(model_access_w_group_id, {
                'perm_delete': False,
                })
            self.test_access.delete(test_ids.pop())

            # Two access rules with both disallowed
            self.model_access.write(model_access_wo_group_id, {
                'perm_delete': False,
                })
            self.failUnlessRaises(Exception, self.test_access.delete,
                    test_ids.pop())

            # One access disallowed for one group
            self.model_access.delete(model_access_wo_group_id)
            self.failUnlessRaises(Exception, self.test_access.delete,
                    test_ids.pop())

            # One access allowed for one group
            self.model_access.write(model_access_w_group_id, {
                'perm_delete': True,
                })
            self.test_access.delete(test_ids.pop())

            # One access allowed for one other group
            group_id = self.group.create({'name': 'Test'})
            self.model_access.write(model_access_w_group_id, {
                'group': group_id,
                })
            self.test_access.delete(test_ids.pop())

            # One access disallowed for one other group
            self.model_access.write(model_access_w_group_id, {
                'perm_delete': False,
                })
            self.test_access.delete(test_ids.pop())

            transaction.cursor.rollback()


class ModelFieldAccessTestCase(unittest.TestCase):
    '''
    Test Model Field Access
    '''

    def setUp(self):
        install_module('test')
        self.field_access = POOL.get('ir.model.field.access')
        self.test_access = POOL.get('test.access')
        self.field = POOL.get('ir.model.field')
        self.group = POOL.get('res.group')

    def test0010perm_read(self):
        '''
        Test Read Access
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            field1_id, = self.field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field1'),
                ])
            field2_id, = self.field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field2'),
                ])

            test_id = self.test_access.create({
                'field1': 'ham',
                'field2': 'spam',
                })

            # Without field access
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # With field access

            # One access allowed for any group
            field_access_wo_group_id = self.field_access.create({
                'field': field1_id,
                'group': False,
                'perm_read': True,
                })
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # One access disallowed for any group
            self.field_access.write(field_access_wo_group_id, {
                'perm_read': False,
                })

            self.failUnlessRaises(Exception, self.test_access.read, test_id,
                    ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id)
            test_access = self.test_access.browse(test_id)
            self.failUnlessRaises(Exception, getattr, test_access, 'field1')
            test_access.field2
            transaction.cursor.cache.clear()

            # Two access rules with one group allowed
            group_id = self.group.search([('users', '=', USER)])[0]
            field_access_w_group_id = self.field_access.create({
                'field': field1_id,
                'group': group_id,
                'perm_read': True,
                })

            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # Two access rules with both allowed
            self.field_access.write(field_access_wo_group_id, {
                'perm_read': True,
                })
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # Two access rules with any group allowed
            self.field_access.write(field_access_w_group_id, {
                'perm_read': False,
                })
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # Two access rules with both disallowed
            self.field_access.write(field_access_wo_group_id, {
                'perm_read': False,
                })
            self.failUnlessRaises(Exception, self.test_access.read, test_id,
                    ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id)
            test_access = self.test_access.browse(test_id)
            self.failUnlessRaises(Exception, getattr, test_access, 'field1')
            test_access.field2
            transaction.cursor.cache.clear()

            # One access disallowed for one group
            self.field_access.delete(field_access_wo_group_id)
            self.failUnlessRaises(Exception, self.test_access.read, test_id,
                    ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id)
            test_access = self.test_access.browse(test_id)
            self.failUnlessRaises(Exception, getattr, test_access, 'field1')
            test_access.field2
            transaction.cursor.cache.clear()

            # One access allowed for one group
            self.field_access.write(field_access_w_group_id, {
                'perm_read': True,
                })
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # One access allowed for one other group
            group_id = self.group.create({'name': 'Test'})
            self.field_access.write(field_access_w_group_id, {
                'group': group_id,
                })
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # One access disallowed for one other group
            self.field_access.write(field_access_w_group_id, {
                'perm_read': False,
                })
            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # Two access rules on both fields allowed
            self.field_access.delete(field_access_w_group_id)

            field_access1 = self.field_access.create({
                'field': field1_id,
                'group': False,
                'perm_read': True,
                })
            field_access2 = self.field_access.create({
                'field': field2_id,
                'group': False,
                'perm_read': True,
                })

            self.test_access.read(test_id, ['field1'])
            self.test_access.read(test_id, ['field2'])
            self.test_access.read(test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            test_access.field2
            transaction.cursor.cache.clear()

            # Two access rules on both fields one allowed and one disallowed
            self.field_access.write(field_access2, {
                'perm_read': False,
                })
            self.test_access.read(test_id, ['field1'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id,
                    ['field2'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id)
            test_access = self.test_access.browse(test_id)
            test_access.field1
            self.failUnlessRaises(Exception, getattr, test_access, 'field2')
            transaction.cursor.cache.clear()

            # Two access rules on both fields disallowed
            self.field_access.write(field_access1, {
                'perm_read': False,
                })
            self.failUnlessRaises(Exception, self.test_access.read, test_id,
                    ['field1'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id,
                    ['field2'])
            self.failUnlessRaises(Exception, self.test_access.read, test_id)
            test_access = self.test_access.browse(test_id)
            self.failUnlessRaises(Exception, getattr, test_access, 'field1')
            self.failUnlessRaises(Exception, getattr, test_access, 'field2')
            transaction.cursor.cache.clear()

            transaction.cursor.rollback()

    def test0010perm_write(self):
        '''
        Test Write Access
        '''
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            field1_id, = self.field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field1'),
                ])
            field2_id, = self.field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field2'),
                ])

            test_id = self.test_access.create({
                'field1': 'ham',
                'field2': 'spam',
                })

            # Without field access
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})

            # With field access

            # One access allowed for any group
            field_access_wo_group_id = self.field_access.create({
                'field': field1_id,
                'group': False,
                'perm_write': True,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # One access disallowed for any group
            self.field_access.write(field_access_wo_group_id, {
                'perm_write': False,
                })

            self.test_access.write(test_id, {})
            self.failUnlessRaises(Exception, self.test_access.write, test_id,
                    {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id, {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules with one group allowed
            group_id = self.group.search([('users', '=', USER)])[0]
            field_access_w_group_id = self.field_access.create({
                'field': field1_id,
                'group': group_id,
                'perm_write': True,
                })

            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # Two access rules with both allowed
            self.field_access.write(field_access_wo_group_id, {
                'perm_write': True,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # Two access rules with any group allowed
            self.field_access.write(field_access_w_group_id, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # Two access rules with both disallowed
            self.field_access.write(field_access_wo_group_id, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})
            self.failUnlessRaises(Exception, self.test_access.write, test_id,
                    {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id, {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access disallowed for one group
            self.field_access.delete(field_access_wo_group_id)
            self.test_access.write(test_id, {})
            self.failUnlessRaises(Exception, self.test_access.write, test_id,
                    {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'ham'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id, {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access allowed for one group
            self.field_access.write(field_access_w_group_id, {
                'perm_write': True,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # One access allowed for one other group
            group_id = self.group.create({'name': 'Test'})
            self.field_access.write(field_access_w_group_id, {
                'group': group_id,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # One access disallowed for one other group
            self.field_access.write(field_access_w_group_id, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # Two access rules on both fields allowed
            self.field_access.delete(field_access_w_group_id)

            field_access1 = self.field_access.create({
                'field': field1_id,
                'group': False,
                'perm_write': True,
                })
            field_access2 = self.field_access.create({
                'field': field2_id,
                'group': False,
                'perm_write': True,
                })

            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.test_access.write(test_id, {'field2': 'spam'})
            self.test_access.write(test_id, {
                'field1': 'ham',
                'field2': 'spam',
                })

            # Two access rules on both fields one allowed and one disallowed
            self.field_access.write(field_access2, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})
            self.test_access.write(test_id, {'field1': 'ham'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id,
                    {'field2': 'spam'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id, {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules on both fields disallowed
            self.field_access.write(field_access1, {
                'perm_write': False,
                })
            self.test_access.write(test_id, {})
            self.failUnlessRaises(Exception, self.test_access.write, test_id,
                    {'field1': 'ham'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id,
                    {'field2': 'spam'})
            self.failUnlessRaises(Exception, self.test_access.write, test_id, {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            transaction.cursor.rollback()

def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelFieldAccessTestCase))
    return suite_

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
