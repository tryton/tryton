# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
        install_module
from trytond.transaction import Transaction
from trytond.exceptions import UserError

CONTEXT = CONTEXT.copy()
CONTEXT['_check_access'] = True


class ModelAccessTestCase(unittest.TestCase):
    'Test Model Access'

    def setUp(self):
        install_module('tests')
        self.model_access = POOL.get('ir.model.access')
        self.test_access = POOL.get('test.access')
        self.model = POOL.get('ir.model')
        self.group = POOL.get('res.group')

    def test0010perm_read(self):
        'Test Read Access'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([('model', '=', 'test.access')])

            test, = self.test_access.create([{}])

            # Without model access
            self.test_access.read([test.id])

            # With model access

            # One access allowed for any group
            model_access_wo_group, = self.model_access.create([{
                        'model': model.id,
                        'group': None,
                        'perm_read': True,
                        }])
            self.test_access.read([test.id])

            # One access disallowed for any group
            self.model_access.write([model_access_wo_group], {
                    'perm_read': False,
                    })
            self.assertRaises(UserError, self.test_access.read, [test.id])

            # Two access rules with one group allowed
            group, = self.group.search([('users', '=', USER)])
            model_access_w_group, = self.model_access.create([{
                        'model': model.id,
                        'group': group.id,
                        'perm_read': True,
                        }])

            self.test_access.read([test.id])

            # Two access rules with both allowed
            self.model_access.write([model_access_wo_group], {
                    'perm_read': True,
                    })
            self.test_access.read([test.id])

            # Two access rules with any group allowed
            self.model_access.write([model_access_w_group], {
                    'perm_read': False,
                    })
            self.test_access.read([test.id])

            # Two access rules with both disallowed
            self.model_access.write([model_access_wo_group], {
                    'perm_read': False,
                    })
            self.assertRaises(UserError, self.test_access.read, [test.id])

            # One access disallowed for one group
            self.model_access.delete([model_access_wo_group])
            self.assertRaises(UserError, self.test_access.read, [test.id])

            # One access allowed for one group
            self.model_access.write([model_access_w_group], {
                    'perm_read': True,
                    })
            self.test_access.read([test.id])

            # One access allowed for one other group
            group, = self.group.create([{'name': 'Test'}])
            self.model_access.write([model_access_w_group], {
                    'group': group.id,
                    })
            self.test_access.read([test.id])

            # One access disallowed for one other group
            self.model_access.write([model_access_w_group], {
                    'perm_read': False,
                    })
            self.test_access.read([test.id])

            transaction.cursor.rollback()
            self.model_access._get_access_cache.clear()

    def test0020perm_write(self):
        'Test Write Access'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([('model', '=', 'test.access')])

            test, = self.test_access.create([{}])

            # Without model access
            self.test_access.write([test], {})

            # With model access

            # One access allowed for any group
            model_access_wo_group, = self.model_access.create([{
                        'model': model.id,
                        'group': None,
                        'perm_write': True,
                        }])
            self.test_access.write([test], {})

            # One access disallowed for any group
            self.model_access.write([model_access_wo_group], {
                    'perm_write': False,
                    })
            self.assertRaises(UserError, self.test_access.write, [test], {})

            # Two access rules with one group allowed
            group, = self.group.search([('users', '=', USER)])
            model_access_w_group, = self.model_access.create([{
                        'model': model.id,
                        'group': group.id,
                        'perm_write': True,
                        }])
            self.test_access.write([test], {})

            # Two access rules with both allowed
            self.model_access.write([model_access_wo_group], {
                    'perm_write': True,
                    })
            self.test_access.write([test], {})

            # Two access rules with any group allowed
            self.model_access.write([model_access_w_group], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})

            # Two access rules with both disallowed
            self.model_access.write([model_access_wo_group], {
                    'perm_write': False,
                    })
            self.assertRaises(UserError, self.test_access.write, [test], {})

            # One access disallowed for one group
            self.model_access.delete([model_access_wo_group])
            self.assertRaises(UserError, self.test_access.write, [test], {})

            # One access allowed for one group
            self.model_access.write([model_access_w_group], {
                    'perm_write': True,
                    })
            self.test_access.write([test], {})

            # One access allowed for one other group
            group, = self.group.create([{'name': 'Test'}])
            self.model_access.write([model_access_w_group], {
                    'group': group.id,
                    })
            self.test_access.write([test], {})

            # One access disallowed for one other group
            self.model_access.write([model_access_w_group], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})

            transaction.cursor.rollback()
            self.model_access._get_access_cache.clear()

    def test0030perm_create(self):
        'Test Create Access'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([('model', '=', 'test.access')])

            # Without model access
            self.test_access.create([{}])

            # With model access

            # One access allowed for any group
            model_access_wo_group, = self.model_access.create([{
                        'model': model.id,
                        'group': None,
                        'perm_create': True,
                        }])
            self.test_access.create([{}])

            # One access disallowed for any group
            self.model_access.write([model_access_wo_group], {
                    'perm_create': False,
                    })
            self.assertRaises(UserError, self.test_access.create, {})

            # Two access rules with one group allowed
            group, = self.group.search([('users', '=', USER)])
            model_access_w_group, = self.model_access.create([{
                        'model': model.id,
                        'group': group.id,
                        'perm_create': True,
                        }])

            self.test_access.create([{}])

            # Two access rules with both allowed
            self.model_access.write([model_access_wo_group], {
                    'perm_create': True,
                    })
            self.test_access.create([{}])

            # Two access rules with any group allowed
            self.model_access.write([model_access_w_group], {
                    'perm_create': False,
                    })
            self.test_access.create([{}])

            # Two access rules with both disallowed
            self.model_access.write([model_access_wo_group], {
                    'perm_create': False,
                    })
            self.assertRaises(UserError, self.test_access.create, [{}])

            # One access disallowed for one group
            self.model_access.delete([model_access_wo_group])
            self.assertRaises(UserError, self.test_access.create, [{}])

            # One access allowed for one group
            self.model_access.write([model_access_w_group], {
                    'perm_create': True,
                    })
            self.test_access.create([{}])

            # One access allowed for one other group
            group, = self.group.create([{'name': 'Test'}])
            self.model_access.write([model_access_w_group], {
                    'group': group.id,
                    })
            self.test_access.create([{}])

            # One access disallowed for one other group
            self.model_access.write([model_access_w_group], {
                    'perm_create': False,
                    })
            self.test_access.create([{}])

            transaction.cursor.rollback()
            self.model_access._get_access_cache.clear()

    def test0040perm_delete(self):
        'Test Delete Access'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            model, = self.model.search([('model', '=', 'test.access')])

            tests = [self.test_access.create([{}])[0] for x in range(11)]

            # Without model access
            self.test_access.delete([tests.pop()])

            # With model access

            # One access allowed for any group
            model_access_wo_group, = self.model_access.create([{
                        'model': model.id,
                        'group': None,
                        'perm_delete': True,
                        }])
            self.test_access.delete([tests.pop()])

            # One access disallowed for any group
            self.model_access.write([model_access_wo_group], {
                    'perm_delete': False,
                    })
            self.assertRaises(UserError, self.test_access.delete,
                [tests.pop()])

            # Two access rules with one group allowed
            group = self.group.search([('users', '=', USER)])[0]
            model_access_w_group, = self.model_access.create([{
                        'model': model.id,
                        'group': group.id,
                        'perm_delete': True,
                        }])

            self.test_access.delete([tests.pop()])

            # Two access rules with both allowed
            self.model_access.write([model_access_wo_group], {
                    'perm_delete': True,
                    })
            self.test_access.delete([tests.pop()])

            # Two access rules with any group allowed
            self.model_access.write([model_access_w_group], {
                    'perm_delete': False,
                    })
            self.test_access.delete([tests.pop()])

            # Two access rules with both disallowed
            self.model_access.write([model_access_wo_group], {
                    'perm_delete': False,
                    })
            self.assertRaises(UserError, self.test_access.delete,
                [tests.pop()])

            # One access disallowed for one group
            self.model_access.delete([model_access_wo_group])
            self.assertRaises(UserError, self.test_access.delete,
                [tests.pop()])

            # One access allowed for one group
            self.model_access.write([model_access_w_group], {
                    'perm_delete': True,
                    })
            self.test_access.delete([tests.pop()])

            # One access allowed for one other group
            group, = self.group.create([{'name': 'Test'}])
            self.model_access.write([model_access_w_group], {
                    'group': group.id,
                    })
            self.test_access.delete([tests.pop()])

            # One access disallowed for one other group
            self.model_access.write([model_access_w_group], {
                    'perm_delete': False,
                    })
            self.test_access.delete([tests.pop()])

            transaction.cursor.rollback()
            self.model_access._get_access_cache.clear()


class ModelFieldAccessTestCase(unittest.TestCase):
    'Test Model Field Access'

    def setUp(self):
        install_module('tests')
        self.field_access = POOL.get('ir.model.field.access')
        self.test_access = POOL.get('test.access')
        self.field = POOL.get('ir.model.field')
        self.group = POOL.get('res.group')

    def test0010perm_read(self):
        'Test Read Access'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            field1, = self.field.search([
                    ('model.model', '=', 'test.access'),
                    ('name', '=', 'field1'),
                    ])
            field2, = self.field.search([
                    ('model.model', '=', 'test.access'),
                    ('name', '=', 'field2'),
                    ])

            test, = self.test_access.create([{
                        'field1': 'ham',
                        'field2': 'spam',
                        }])

            # Without field access
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # With field access

            # One access allowed for any group
            field_access_wo_group, = self.field_access.create([{
                        'field': field1.id,
                        'group': None,
                        'perm_read': True,
                        }])
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # One access disallowed for any group
            self.field_access.write([field_access_wo_group], {
                    'perm_read': False,
                    })

            self.assertRaises(UserError, self.test_access.read, [test.id],
                ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.assertRaises(UserError, self.test_access.read, [test.id])
            self.assertRaises(UserError, getattr, test, 'field1')
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules with one group allowed
            group = self.group.search([('users', '=', USER)])[0]
            field_access_w_group, = self.field_access.create([{
                        'field': field1.id,
                        'group': group.id,
                        'perm_read': True,
                        }])

            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules with both allowed
            self.field_access.write([field_access_wo_group], {
                    'perm_read': True,
                    })
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules with any group allowed
            self.field_access.write([field_access_w_group], {
                    'perm_read': False,
                    })
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules with both disallowed
            self.field_access.write([field_access_wo_group], {
                'perm_read': False,
                })
            self.assertRaises(UserError, self.test_access.read, [test.id],
                ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.assertRaises(UserError, self.test_access.read, [test.id])
            self.assertRaises(UserError, getattr, test, 'field1')
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # One access disallowed for one group
            self.field_access.delete([field_access_wo_group])
            self.assertRaises(UserError, self.test_access.read, [test.id],
                ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.assertRaises(UserError, self.test_access.read, [test.id])
            self.assertRaises(UserError, getattr, test, 'field1')
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # One access allowed for one group
            self.field_access.write([field_access_w_group], {
                    'perm_read': True,
                    })
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # One access allowed for one other group
            group, = self.group.create([{'name': 'Test'}])
            self.field_access.write([field_access_w_group], {
                    'group': group.id,
                    })
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # One access disallowed for one other group
            self.field_access.write([field_access_w_group], {
                    'perm_read': False,
                    })
            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules on both fields allowed
            self.field_access.delete([field_access_w_group])

            field_access1, = self.field_access.create([{
                        'field': field1.id,
                        'group': None,
                        'perm_read': True,
                        }])
            field_access2, = self.field_access.create([{
                        'field': field2.id,
                        'group': None,
                        'perm_read': True,
                        }])

            self.test_access.read([test.id], ['field1'])
            self.test_access.read([test.id], ['field2'])
            self.test_access.read([test.id])
            test.field1
            test.field2
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules on both fields one allowed and one disallowed
            self.field_access.write([field_access2], {
                'perm_read': False,
                })
            self.test_access.read([test.id], ['field1'])
            self.assertRaises(UserError, self.test_access.read, [test.id],
                ['field2'])
            self.assertRaises(UserError, self.test_access.read, [test.id])
            test.field1
            self.assertRaises(UserError, getattr, test, 'field2')
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            # Two access rules on both fields disallowed
            self.field_access.write([field_access1], {
                    'perm_read': False,
                    })
            self.assertRaises(UserError, self.test_access.read, [test.id],
                ['field1'])
            self.assertRaises(UserError, self.test_access.read, [test.id],
                ['field2'])
            self.assertRaises(UserError, self.test_access.read, [test.id])
            self.assertRaises(UserError, getattr, test, 'field1')
            self.assertRaises(UserError, getattr, test, 'field2')
            transaction.cursor.cache.clear()
            test = self.test_access(test.id)

            transaction.cursor.rollback()
            self.field_access._get_access_cache.clear()

    def test0010perm_write(self):
        'Test Write Access'
        with Transaction().start(DB_NAME, USER,
                context=CONTEXT) as transaction:
            field1, = self.field.search([
                    ('model.model', '=', 'test.access'),
                    ('name', '=', 'field1'),
                    ])
            field2, = self.field.search([
                    ('model.model', '=', 'test.access'),
                    ('name', '=', 'field2'),
                    ])

            test, = self.test_access.create([{
                        'field1': 'ham',
                        'field2': 'spam',
                        }])

            # Without field access
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})

            # With field access

            # One access allowed for any group
            field_access_wo_group, = self.field_access.create([{
                        'field': field1.id,
                        'group': None,
                        'perm_write': True,
                        }])
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access disallowed for any group
            self.field_access.write([field_access_wo_group], {
                    'perm_write': False,
                    })

            self.test_access.write([test], {})
            self.assertRaises(UserError, self.test_access.write, [test],
                {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules with one group allowed
            group = self.group.search([('users', '=', USER)])[0]
            field_access_w_group, = self.field_access.create([{
                        'field': field1.id,
                        'group': group.id,
                        'perm_write': True,
                        }])

            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules with both allowed
            self.field_access.write([field_access_wo_group], {
                    'perm_write': True,
                    })
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules with any group allowed
            self.field_access.write([field_access_w_group], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules with both disallowed
            self.field_access.write([field_access_wo_group], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})
            self.assertRaises(UserError, self.test_access.write, [test],
                {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access disallowed for one group
            self.field_access.delete([field_access_wo_group])
            self.test_access.write([test], {})
            self.assertRaises(UserError, self.test_access.write, [test],
                {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'ham'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access allowed for one group
            self.field_access.write([field_access_w_group], {
                    'perm_write': True,
                    })
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access allowed for one other group
            group, = self.group.create([{'name': 'Test'}])
            self.field_access.write([field_access_w_group], {
                    'group': group.id,
                    })
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # One access disallowed for one other group
            self.field_access.write([field_access_w_group], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules on both fields allowed
            self.field_access.delete([field_access_w_group])

            field_access1, = self.field_access.create([{
                        'field': field1.id,
                        'group': None,
                        'perm_write': True,
                        }])
            field_access2, = self.field_access.create([{
                        'field': field2.id,
                        'group': None,
                        'perm_write': True,
                        }])

            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.test_access.write([test], {'field2': 'spam'})
            self.test_access.write([test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules on both fields one allowed and one disallowed
            self.field_access.write([field_access2], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})
            self.test_access.write([test], {'field1': 'ham'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field2': 'spam'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            # Two access rules on both fields disallowed
            self.field_access.write([field_access1], {
                    'perm_write': False,
                    })
            self.test_access.write([test], {})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field1': 'ham'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field2': 'spam'})
            self.assertRaises(UserError, self.test_access.write, [test], {
                    'field1': 'ham',
                    'field2': 'spam',
                    })

            transaction.cursor.rollback()
            self.field_access._get_access_cache.clear()


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelFieldAccessTestCase))
    return suite_
