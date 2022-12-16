# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.exceptions import UserError

_context = {'_check_access': True}


class ModelAccessTestCase(unittest.TestCase):
    'Test Model Access'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction(context=_context)
    def test_perm_read(self):
        'Test Read Access'
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get('test.access')
        Model = pool.get('ir.model')
        Group = pool.get('res.group')

        model, = Model.search([('model', '=', 'test.access')])

        test, = TestAccess.create([{}])

        # Without model access
        TestAccess.read([test.id])

        # With model access

        # One access allowed for any group
        model_access_wo_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': None,
                    'perm_read': True,
                    }])
        TestAccess.read([test.id])

        # One access disallowed for any group
        ModelAccess.write([model_access_wo_group], {
                'perm_read': False,
                })
        self.assertRaises(UserError, TestAccess.read, [test.id])

        # Two access rules with one group allowed
        group, = Group.search([('users', '=', Transaction().user)])
        model_access_w_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': group.id,
                    'perm_read': True,
                    }])

        TestAccess.read([test.id])

        # Two access rules with both allowed
        ModelAccess.write([model_access_wo_group], {
                'perm_read': True,
                })
        TestAccess.read([test.id])

        # Two access rules with any group allowed
        ModelAccess.write([model_access_w_group], {
                'perm_read': False,
                })
        TestAccess.read([test.id])

        # Two access rules with both disallowed
        ModelAccess.write([model_access_wo_group], {
                'perm_read': False,
                })
        self.assertRaises(UserError, TestAccess.read, [test.id])

        # One access disallowed for one group
        ModelAccess.delete([model_access_wo_group])
        self.assertRaises(UserError, TestAccess.read, [test.id])

        # One access allowed for one group
        ModelAccess.write([model_access_w_group], {
                'perm_read': True,
                })
        TestAccess.read([test.id])

        # One access allowed for one other group
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.write([model_access_w_group], {
                'group': group.id,
                })
        TestAccess.read([test.id])

        # One access disallowed for one other group
        ModelAccess.write([model_access_w_group], {
                'perm_read': False,
                })
        TestAccess.read([test.id])

    @with_transaction(context=_context)
    def test_perm_write(self):
        'Test Write Access'
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get('test.access')
        Model = pool.get('ir.model')
        Group = pool.get('res.group')

        model, = Model.search([('model', '=', 'test.access')])

        test, = TestAccess.create([{}])

        # Without model access
        TestAccess.write([test], {})

        # With model access

        # One access allowed for any group
        model_access_wo_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': None,
                    'perm_write': True,
                    }])
        TestAccess.write([test], {})

        # One access disallowed for any group
        ModelAccess.write([model_access_wo_group], {
                'perm_write': False,
                })
        self.assertRaises(UserError, TestAccess.write, [test], {})

        # Two access rules with one group allowed
        group, = Group.search([('users', '=', Transaction().user)])
        model_access_w_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': group.id,
                    'perm_write': True,
                    }])
        TestAccess.write([test], {})

        # Two access rules with both allowed
        ModelAccess.write([model_access_wo_group], {
                'perm_write': True,
                })
        TestAccess.write([test], {})

        # Two access rules with any group allowed
        ModelAccess.write([model_access_w_group], {
                'perm_write': False,
                })
        TestAccess.write([test], {})

        # Two access rules with both disallowed
        ModelAccess.write([model_access_wo_group], {
                'perm_write': False,
                })
        self.assertRaises(UserError, TestAccess.write, [test], {})

        # One access disallowed for one group
        ModelAccess.delete([model_access_wo_group])
        self.assertRaises(UserError, TestAccess.write, [test], {})

        # One access allowed for one group
        ModelAccess.write([model_access_w_group], {
                'perm_write': True,
                })
        TestAccess.write([test], {})

        # One access allowed for one other group
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.write([model_access_w_group], {
                'group': group.id,
                })
        TestAccess.write([test], {})

        # One access disallowed for one other group
        ModelAccess.write([model_access_w_group], {
                'perm_write': False,
                })
        TestAccess.write([test], {})

    @with_transaction(context=_context)
    def test_perm_create(self):
        'Test Create Access'
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get('test.access')
        Model = pool.get('ir.model')
        Group = pool.get('res.group')

        model, = Model.search([('model', '=', 'test.access')])

        # Without model access
        TestAccess.create([{}])

        # With model access

        # One access allowed for any group
        model_access_wo_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': None,
                    'perm_create': True,
                    }])
        TestAccess.create([{}])

        # One access disallowed for any group
        ModelAccess.write([model_access_wo_group], {
                'perm_create': False,
                })
        self.assertRaises(UserError, TestAccess.create, {})

        # Two access rules with one group allowed
        group, = Group.search([('users', '=', Transaction().user)])
        model_access_w_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': group.id,
                    'perm_create': True,
                    }])

        TestAccess.create([{}])

        # Two access rules with both allowed
        ModelAccess.write([model_access_wo_group], {
                'perm_create': True,
                })
        TestAccess.create([{}])

        # Two access rules with any group allowed
        ModelAccess.write([model_access_w_group], {
                'perm_create': False,
                })
        TestAccess.create([{}])

        # Two access rules with both disallowed
        ModelAccess.write([model_access_wo_group], {
                'perm_create': False,
                })
        self.assertRaises(UserError, TestAccess.create, [{}])

        # One access disallowed for one group
        ModelAccess.delete([model_access_wo_group])
        self.assertRaises(UserError, TestAccess.create, [{}])

        # One access allowed for one group
        ModelAccess.write([model_access_w_group], {
                'perm_create': True,
                })
        TestAccess.create([{}])

        # One access allowed for one other group
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.write([model_access_w_group], {
                'group': group.id,
                })
        TestAccess.create([{}])

        # One access disallowed for one other group
        ModelAccess.write([model_access_w_group], {
                'perm_create': False,
                })
        TestAccess.create([{}])

    @with_transaction(context=_context)
    def test_perm_delete(self):
        'Test Delete Access'
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        TestAccess = pool.get('test.access')
        Model = pool.get('ir.model')
        Group = pool.get('res.group')

        model, = Model.search([('model', '=', 'test.access')])

        tests = [TestAccess.create([{}])[0] for x in range(11)]

        # Without model access
        TestAccess.delete([tests.pop()])

        # With model access

        # One access allowed for any group
        model_access_wo_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': None,
                    'perm_delete': True,
                    }])
        TestAccess.delete([tests.pop()])

        # One access disallowed for any group
        ModelAccess.write([model_access_wo_group], {
                'perm_delete': False,
                })
        self.assertRaises(UserError, TestAccess.delete, [tests.pop()])

        # Two access rules with one group allowed
        group = Group.search([('users', '=', Transaction().user)])[0]
        model_access_w_group, = ModelAccess.create([{
                    'model': model.id,
                    'group': group.id,
                    'perm_delete': True,
                    }])

        TestAccess.delete([tests.pop()])

        # Two access rules with both allowed
        ModelAccess.write([model_access_wo_group], {
                'perm_delete': True,
                })
        TestAccess.delete([tests.pop()])

        # Two access rules with any group allowed
        ModelAccess.write([model_access_w_group], {
                'perm_delete': False,
                })
        TestAccess.delete([tests.pop()])

        # Two access rules with both disallowed
        ModelAccess.write([model_access_wo_group], {
                'perm_delete': False,
                })
        self.assertRaises(UserError, TestAccess.delete, [tests.pop()])

        # One access disallowed for one group
        ModelAccess.delete([model_access_wo_group])
        self.assertRaises(UserError, TestAccess.delete, [tests.pop()])

        # One access allowed for one group
        ModelAccess.write([model_access_w_group], {
                'perm_delete': True,
                })
        TestAccess.delete([tests.pop()])

        # One access allowed for one other group
        group, = Group.create([{'name': 'Test'}])
        ModelAccess.write([model_access_w_group], {
                'group': group.id,
                })
        TestAccess.delete([tests.pop()])

        # One access disallowed for one other group
        ModelAccess.write([model_access_w_group], {
                'perm_delete': False,
                })
        TestAccess.delete([tests.pop()])


class ModelFieldAccessTestCase(unittest.TestCase):
    'Test Model Field Access'

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction(context=_context)
    def test0010perm_read(self):
        'Test Read Access'
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        Field = pool.get('ir.model.field')
        Group = pool.get('res.group')
        transaction = Transaction()

        field1, = Field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field1'),
                ])
        field2, = Field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field2'),
                ])

        test, = TestAccess.create([{
                    'field1': 'ham',
                    'field2': 'spam',
                    }])

        # Without field access
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # With field access

        # One access allowed for any group
        field_access_wo_group, = FieldAccess.create([{
                    'field': field1.id,
                    'group': None,
                    'perm_read': True,
                    }])
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # One access disallowed for any group
        FieldAccess.write([field_access_wo_group], {
                'perm_read': False,
                })

        self.assertRaises(UserError, TestAccess.read, [test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        self.assertRaises(UserError, TestAccess.read, [test.id])
        self.assertRaises(UserError, getattr, test, 'field1')
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules with one group allowed
        group = Group.search([('users', '=', transaction.user)])[0]
        field_access_w_group, = FieldAccess.create([{
                    'field': field1.id,
                    'group': group.id,
                    'perm_read': True,
                    }])

        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules with both allowed
        FieldAccess.write([field_access_wo_group], {
                'perm_read': True,
                })
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules with any group allowed
        FieldAccess.write([field_access_w_group], {
                'perm_read': False,
                })
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules with both disallowed
        FieldAccess.write([field_access_wo_group], {
            'perm_read': False,
            })
        self.assertRaises(UserError, TestAccess.read, [test.id],
            ['field1'])
        TestAccess.read([test.id], ['field2'])
        self.assertRaises(UserError, TestAccess.read, [test.id])
        self.assertRaises(UserError, getattr, test, 'field1')
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # One access disallowed for one group
        FieldAccess.delete([field_access_wo_group])
        self.assertRaises(UserError, TestAccess.read, [test.id],
            ['field1'])
        TestAccess.read([test.id], ['field2'])
        self.assertRaises(UserError, TestAccess.read, [test.id])
        self.assertRaises(UserError, getattr, test, 'field1')
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # One access allowed for one group
        FieldAccess.write([field_access_w_group], {
                'perm_read': True,
                })
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # One access allowed for one other group
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.write([field_access_w_group], {
                'group': group.id,
                })
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # One access disallowed for one other group
        FieldAccess.write([field_access_w_group], {
                'perm_read': False,
                })
        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules on both fields allowed
        FieldAccess.delete([field_access_w_group])

        field_access1, = FieldAccess.create([{
                    'field': field1.id,
                    'group': None,
                    'perm_read': True,
                    }])
        field_access2, = FieldAccess.create([{
                    'field': field2.id,
                    'group': None,
                    'perm_read': True,
                    }])

        TestAccess.read([test.id], ['field1'])
        TestAccess.read([test.id], ['field2'])
        TestAccess.read([test.id])
        test.field1
        test.field2
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules on both fields one allowed and one disallowed
        FieldAccess.write([field_access2], {
            'perm_read': False,
            })
        TestAccess.read([test.id], ['field1'])
        self.assertRaises(UserError, TestAccess.read, [test.id],
            ['field2'])
        self.assertRaises(UserError, TestAccess.read, [test.id])
        test.field1
        self.assertRaises(UserError, getattr, test, 'field2')
        transaction.cache.clear()
        test = TestAccess(test.id)

        # Two access rules on both fields disallowed
        FieldAccess.write([field_access1], {
                'perm_read': False,
                })
        self.assertRaises(UserError, TestAccess.read, [test.id],
            ['field1'])
        self.assertRaises(UserError, TestAccess.read, [test.id],
            ['field2'])
        self.assertRaises(UserError, TestAccess.read, [test.id])
        self.assertRaises(UserError, getattr, test, 'field1')
        self.assertRaises(UserError, getattr, test, 'field2')
        transaction.cache.clear()
        test = TestAccess(test.id)

    @with_transaction(context=_context)
    def test_perm_write(self):
        'Test Write Access'
        pool = Pool()
        FieldAccess = pool.get('ir.model.field.access')
        TestAccess = pool.get('test.access')
        Field = pool.get('ir.model.field')
        Group = pool.get('res.group')
        transaction = Transaction()

        field1, = Field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field1'),
                ])
        field2, = Field.search([
                ('model.model', '=', 'test.access'),
                ('name', '=', 'field2'),
                ])

        test, = TestAccess.create([{
                    'field1': 'ham',
                    'field2': 'spam',
                    }])

        # Without field access
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})

        # With field access

        # One access allowed for any group
        field_access_wo_group, = FieldAccess.create([{
                    'field': field1.id,
                    'group': None,
                    'perm_write': True,
                    }])
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # One access disallowed for any group
        FieldAccess.write([field_access_wo_group], {
                'perm_write': False,
                })

        TestAccess.write([test], {})
        self.assertRaises(UserError, TestAccess.write, [test],
            {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field1': 'ham',
                'field2': 'spam',
                })
        self.assertRaises(UserError, TestAccess.write,
            [test], {'field2': 'spam'}, [test], {'field1': 'ham'})

        # Two access rules with one group allowed
        group = Group.search([('users', '=', transaction.user)])[0]
        field_access_w_group, = FieldAccess.create([{
                    'field': field1.id,
                    'group': group.id,
                    'perm_write': True,
                    }])

        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # Two access rules with both allowed
        FieldAccess.write([field_access_wo_group], {
                'perm_write': True,
                })
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # Two access rules with any group allowed
        FieldAccess.write([field_access_w_group], {
                'perm_write': False,
                })
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # Two access rules with both disallowed
        FieldAccess.write([field_access_wo_group], {
                'perm_write': False,
                })
        TestAccess.write([test], {})
        self.assertRaises(UserError, TestAccess.write, [test],
            {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # One access disallowed for one group
        FieldAccess.delete([field_access_wo_group])
        TestAccess.write([test], {})
        self.assertRaises(UserError, TestAccess.write, [test],
            {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'ham'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # One access allowed for one group
        FieldAccess.write([field_access_w_group], {
                'perm_write': True,
                })
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # One access allowed for one other group
        group, = Group.create([{'name': 'Test'}])
        FieldAccess.write([field_access_w_group], {
                'group': group.id,
                })
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # One access disallowed for one other group
        FieldAccess.write([field_access_w_group], {
                'perm_write': False,
                })
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # Two access rules on both fields allowed
        FieldAccess.delete([field_access_w_group])

        field_access1, = FieldAccess.create([{
                    'field': field1.id,
                    'group': None,
                    'perm_write': True,
                    }])
        field_access2, = FieldAccess.create([{
                    'field': field2.id,
                    'group': None,
                    'perm_write': True,
                    }])

        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        TestAccess.write([test], {'field2': 'spam'})
        TestAccess.write([test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # Two access rules on both fields one allowed and one disallowed
        FieldAccess.write([field_access2], {
                'perm_write': False,
                })
        TestAccess.write([test], {})
        TestAccess.write([test], {'field1': 'ham'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field2': 'spam'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field1': 'ham',
                'field2': 'spam',
                })

        # Two access rules on both fields disallowed
        FieldAccess.write([field_access1], {
                'perm_write': False,
                })
        TestAccess.write([test], {})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field1': 'ham'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field2': 'spam'})
        self.assertRaises(UserError, TestAccess.write, [test], {
                'field1': 'ham',
                'field2': 'spam',
                })


def suite():
    suite_ = unittest.TestSuite()
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelAccessTestCase))
    suite_.addTests(unittest.TestLoader(
        ).loadTestsFromTestCase(ModelFieldAccessTestCase))
    return suite_
