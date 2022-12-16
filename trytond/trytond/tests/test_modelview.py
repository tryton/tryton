# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from unittest.mock import patch

from lxml import etree

from trytond.model.exceptions import AccessError, AccessButtonError
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, Eval


class ModelView(unittest.TestCase):
    "Test ModelView"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_changed_values(self):
        "Test ModelView._changed_values"
        pool = Pool()
        Model = pool.get('test.modelview.changed_values')
        Target = pool.get('test.modelview.changed_values.target')

        record = Model()

        self.assertEqual(record._changed_values, {})

        record.name = 'foo'
        record.target = Target(1)
        record.ref_target = Target(2)
        record.targets = [Target(name='bar')]
        self.assertEqual(record._changed_values, {
                'name': 'foo',
                'target': 1,
                'ref_target': 'test.modelview.changed_values.target,2',
                'targets': {
                    'add': [
                        (0, {'name': 'bar'}),
                        ],
                    },
                })

        record = Model(name='test', target=1, targets=[
                {'id': 1, 'name': 'foo'},
                {'id': 2},
                ], m2m_targets=[5, 6, 7])

        self.assertEqual(record._changed_values, {})

        target = record.targets[0]
        target.name = 'bar'
        record.targets = [target]
        record.m2m_targets = [Target(9), Target(10)]
        self.assertEqual(record._changed_values, {
                'targets': {
                    'update': [{'id': 1, 'name': 'bar'}],
                    'remove': [2],
                    },
                'm2m_targets': [9, 10],
                })

        # change only one2many record
        record = Model(targets=[{'id': 1, 'name': 'foo'}])
        self.assertEqual(record._changed_values, {})

        target, = record.targets
        target.name = 'bar'
        record.targets = record.targets
        self.assertEqual(record._changed_values, {
                'targets': {
                    'update': [{'id': 1, 'name': 'bar'}],
                    },
                })

        # no initial value
        record = Model()
        record._values = {}
        target = Target(id=1)
        record._values['targets'] = [target]
        target.name = 'foo'
        self.assertEqual(record._changed_values, {
                'targets': {
                    'update': [{'id': 1, 'name': 'foo'}],
                    },
                })

    @with_transaction()
    def test_changed_values_rec_name(self):
        "Test rec_name of ModelStorage is added"
        pool = Pool()
        Model = pool.get('test.modelview.changed_values')
        Target = pool.get('test.modelview.changed_values.stored_target')

        target, = Target.create([{'name': "Target"}])
        record = Model()
        record.stored_target = target

        self.assertEqual(record._changed_values, {
                'stored_target': target.id,
                'stored_target.': {
                    'rec_name': "Target",
                    },
                })

    @with_transaction(context={'_check_access': True})
    def test_button_access(self):
        'Test Button Access'
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        Model = pool.get('ir.model')
        Button = pool.get('ir.model.button')
        ModelAccess = pool.get('ir.model.access')
        Group = pool.get('res.group')

        model, = Model.search([('model', '=', 'test.modelview.button')])
        admin, = Group.search([('name', '=', 'Administration')])
        test = TestModel()

        button = Button(name='test', model=model)
        button.save()

        # Without model/button access
        TestModel.test([test])

        # Without read access
        access = ModelAccess(model=model, group=None, perm_read=False)
        access.save()
        with self.assertRaises(AccessError):
            TestModel.test([test])

        # Without write access
        access.perm_read = True
        access.perm_write = False
        access.save()
        with self.assertRaises(AccessError):
            TestModel.test([test])

        # Without write access but with button access
        button.groups = [admin]
        button.save()
        TestModel.test([test])

        # Without button access
        ModelAccess.delete([access])
        no_group = Group(name='no group')
        no_group.save()
        button.groups = [no_group]
        button.save()
        with self.assertRaises(AccessButtonError):
            TestModel.test([test])

    @with_transaction(context={'_check_access': True})
    def test_button_no_rule(self):
        "Test no Button Rule"
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        ButtonClick = pool.get('ir.model.button.click')

        record = TestModel(id=-1)
        with patch.object(TestModel, 'test_non_decorated') as button_func:
            TestModel.test([record])
            button_func.assert_called_with([record])

        clicks = ButtonClick.search([
                ('record_id', '=', record.id),
                ])
        self.assertEqual(len(clicks), 0)

    @with_transaction(context={'_check_access': True})
    def test_button_rule_not_passed(self):
        "Test not passed Button Rule"
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        Model = pool.get('ir.model')
        Button = pool.get('ir.model.button')
        ButtonRule = pool.get('ir.model.button.rule')
        ButtonClick = pool.get('ir.model.button.click')

        model, = Model.search([('model', '=', 'test.modelview.button')])
        rule = ButtonRule(number_user=2)
        button = Button(name='test', model=model, rules=[rule])
        button.save()

        record = TestModel(id=-1)
        with patch.object(TestModel, 'test_non_decorated') as button_func:
            TestModel.test([record])
            button_func.assert_called_with([])

        clicks = ButtonClick.search([
                ('button', '=', button.id),
                ('record_id', '=', record.id),
                ])
        self.assertEqual(len(clicks), 1)
        click, = clicks
        self.assertEqual(click.user.id, 1)

    @with_transaction(context={'_check_access': True})
    def test_button_rule_passed(self):
        "Test passed Button Rule"
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        Model = pool.get('ir.model')
        Button = pool.get('ir.model.button')
        ButtonRule = pool.get('ir.model.button.rule')
        ButtonClick = pool.get('ir.model.button.click')

        model, = Model.search([('model', '=', 'test.modelview.button')])
        rule = ButtonRule(number_user=1)
        button = Button(name='test', model=model, rules=[rule])
        button.save()

        record = TestModel(id=-1)
        with patch.object(TestModel, 'test_non_decorated') as button_func:
            TestModel.test([record])
            button_func.assert_called_with([record])

        clicks = ButtonClick.search([
                ('button', '=', button.id),
                ('record_id', '=', record.id),
                ])
        self.assertEqual(len(clicks), 1)
        click, = clicks
        self.assertEqual(click.user.id, 1)

    @with_transaction()
    def test_button_rule_test_condition(self):
        "Test condition Button Rule"
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        Button = pool.get('ir.model.button')
        ButtonRule = pool.get('ir.model.button.rule')
        ButtonClick = pool.get('ir.model.button.click')

        button = Button()
        clicks = [ButtonClick(user=1)]
        condition = PYSONEncoder().encode(
            Eval('self', {}).get('value', 0) > 48)
        rule = ButtonRule(
            condition=condition, group=None, number_user=2, button=button)
        record = TestModel(id=-1)

        record.value = 10
        self.assertTrue(rule.test(record, clicks))

        record.value = 50
        self.assertFalse(rule.test(record, clicks))

    @with_transaction()
    def test_button_rule_test_group(self):
        "Test group Button Rule"
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        Button = pool.get('ir.model.button')
        ButtonRule = pool.get('ir.model.button.rule')
        ButtonClick = pool.get('ir.model.button.click')
        User = pool.get('res.user')
        Group = pool.get('res.group')

        group = Group()
        user = User()
        user.groups = []
        button = Button()
        clicks = [ButtonClick(user=user)]
        rule = ButtonRule(
            condition=None, group=group, number_user=1, button=button)
        record = TestModel()

        self.assertFalse(rule.test(record, clicks))

        user.groups = [group]
        self.assertTrue(rule.test(record, clicks))

    @with_transaction()
    def test_button_rule_test_number_user(self):
        "Test number user Button Rule"
        pool = Pool()
        TestModel = pool.get('test.modelview.button')
        Button = pool.get('ir.model.button')
        ButtonRule = pool.get('ir.model.button.rule')
        ButtonClick = pool.get('ir.model.button.click')
        User = pool.get('res.user')

        user1 = User()
        user2 = User()
        button = Button()
        rule = ButtonRule(
            condition=None, group=None, number_user=2, button=button)
        record = TestModel()

        # No click
        self.assertFalse(rule.test(record, []))

        # Only one click
        clicks = [ButtonClick(user=user1)]
        self.assertFalse(rule.test(record, clicks))

        # Two clicks from the same user
        clicks = [ButtonClick(user=user1), ButtonClick(user=user1)]
        self.assertFalse(rule.test(record, clicks))

        # Two clicks from different users
        clicks = [ButtonClick(user=user1), ButtonClick(user=user2)]
        self.assertTrue(rule.test(record, clicks))

    @with_transaction()
    def test_rpc_setup(self):
        "Testing the computation of the RPC methods"
        pool = Pool()
        TestModel = pool.get('test.modelview.rpc')

        def check_rpc(rpc, attributes):
            for key, value in attributes.items():
                self.assertEqual(getattr(rpc, key), value)

        NO_INSTANTIATION = {
            'instantiate': None,
            }
        INSTANTIATE_FIRST = {
            'instantiate': 0,
            }
        for rpc_name, rpc_attrs in [
                ('get_selection', NO_INSTANTIATION),
                ('get_function_selection', NO_INSTANTIATION),
                ('get_reference', NO_INSTANTIATION),
                ('get_function_reference', NO_INSTANTIATION),
                ('on_change_with_integer', INSTANTIATE_FIRST),
                ('on_change_float', INSTANTIATE_FIRST),
                ('autocomplete_char', INSTANTIATE_FIRST),
                ]:
            self.assertIn(rpc_name, TestModel.__rpc__)
            check_rpc(TestModel.__rpc__[rpc_name], rpc_attrs)

    @with_transaction()
    def test_remove_empty_page(self):
        "Testing the removal of empty pages"
        pool = Pool()
        EmptyPage = pool.get('test.modelview.empty_page')

        arch = EmptyPage.fields_view_get(view_type='form')['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        pages = tree.xpath('//page')
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].attrib['id'], 'non-empty')

    @with_transaction()
    def test_active_field(self):
        "Testing active field is set and added to view fields"
        pool = Pool()
        Deactivable = pool.get('test.deactivable.modelview')
        EmptyPage = pool.get('test.modelview.empty_page')

        fields = Deactivable.fields_view_get(view_type='tree')['fields']
        self.assertIn('active', fields)

        fields = EmptyPage.fields_view_get(view_type='tree')['fields']
        self.assertNotIn('active', fields)

    @with_transaction(context={'_check_access': True})
    def test_circular_depends_removed(self):
        "Testing circular depends are removed when user has no access"
        pool = Pool()
        CircularDepends = pool.get('test.modelview.circular_depends')
        Field = pool.get('ir.model.field')
        FieldAccess = pool.get('ir.model.field.access')

        foo_field, = Field.search([
                ('model.model', '=', 'test.modelview.circular_depends'),
                ('name', '=', 'foo'),
                ])
        FieldAccess.create([{
            'field': foo_field.id,
            'group': None,
            'perm_read': False,
            }])

        fields = CircularDepends.fields_view_get(view_type='form')['fields']

        self.assertEqual(fields, {})

    @with_transaction(context={'_check_access': True})
    def test_button_depends_access(self):
        "Testing buttons are not removed when dependant fields are accesible"
        pool = Pool()
        Button = pool.get('test.modelview.button_depends')

        arch = Button.fields_view_get(view_type='form')['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        buttons = tree.xpath('//button')

        self.assertEqual(len(buttons), 1)

    @with_transaction(context={'_check_access': True})
    def test_button_depends_no_access(self):
        "Testing buttons are removed when dependant fields are not accesible"
        pool = Pool()
        Button = pool.get('test.modelview.button_depends')
        Field = pool.get('ir.model.field')
        FieldAccess = pool.get('ir.model.field.access')

        field, = Field.search([
                ('model.model', '=', Button.__name__),
                ('name', '=', 'value'),
                ])
        FieldAccess.create([{
            'field': field.id,
            'group': None,
            'perm_read': False,
            }])

        arch = Button.fields_view_get(view_type='form')['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        buttons = tree.xpath('//button')

        self.assertEqual(len(buttons), 0)


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (ModelView,):
        suite.addTests(func(testcase))
    return suite
