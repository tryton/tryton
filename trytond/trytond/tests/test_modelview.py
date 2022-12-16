# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
from unittest.mock import patch

from lxml import etree

from trytond.model.exceptions import AccessError, AccessButtonError
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder, PYSONDecoder, Eval


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
        record.multiselection = ['a']
        record.dictionary = {'key': 'value'}
        self.assertEqual(record._changed_values, {
                'name': 'foo',
                'target': 1,
                'ref_target': 'test.modelview.changed_values.target,2',
                'targets': {
                    'add': [
                        (0, {'id': None, 'name': 'bar'}),
                        ],
                    },
                'multiselection': ('a',),
                'dictionary': {'key': 'value'},
                })

        record = Model(name='test', target=1, targets=[
                {'id': 1, 'name': 'foo'},
                {'id': 2},
                ],
            m2m_targets=[5, 6, 7],
            multiselection=['a'],
            dictionary={'key': 'value'},
            )

        self.assertEqual(record._changed_values, {})

        target = record.targets[0]
        target.name = 'bar'
        record.targets = [target]
        record.m2m_targets = [Target(9), Target(10)]
        ms = list(record.multiselection)
        ms.append('b')
        record.multiselection = ms
        dico = record.dictionary.copy()
        dico['key'] = 'another value'
        record.dictionary = dico
        self.assertEqual(record._changed_values, {
                'targets': {
                    'update': [{'id': 1, 'name': 'bar'}],
                    'delete': [2],
                    },
                'm2m_targets': {
                    'remove': [5, 6, 7],
                    'add': [(0, {'id': 9}), (1, {'id': 10})],
                    },
                'multiselection': ('a', 'b'),
                'dictionary': {'key': 'another value'},
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
        record._values = record._record()
        target = Target(id=1)
        record._values['targets'] = [target]
        target.name = 'foo'
        self.assertEqual(record._changed_values, {
                'targets': {
                    'add': [(0, {'id': 1, 'name': 'foo'})],
                    },
                })

    @with_transaction()
    def test_changed_values_stored(self):
        "Test stored changed values"
        pool = Pool()
        Model = pool.get('test.modelview.stored.changed_values')
        Target = pool.get('test.modelview.stored.changed_values.target')

        record = Model()
        record.targets = [Target(name="foo"), Target(name="bar")]
        record.save()
        target1, target2 = record.targets

        record = Model(record.id)
        target1.name = "test"
        record.targets = [target1, Target(name="baz")]

        self.assertEqual(record._changed_values, {
                'targets': {
                    'delete': [target2.id],
                    'update': [{'id': target1.id, 'name': "test"}],
                    'add': [(1, {'id': None, 'name': "baz"})],
                    },
                })

    @with_transaction()
    def test_changed_values_removed(self):
        "Test removed"
        pool = Pool()
        Model = pool.get('test.modelview.changed_values')
        Target = pool.get('test.modelview.changed_values.target')

        target = Target(1)
        record = Model(targets=[target])
        Model.targets.remove(record, [target])

        self.assertEqual(record._changed_values, {
                'targets': {
                    'remove': [1],
                    },
                })

    @with_transaction()
    def test_changed_values_deleted(self):
        "Test deleted"
        pool = Pool()
        Model = pool.get('test.modelview.changed_values')
        Target = pool.get('test.modelview.changed_values.target')

        target = Target(1)
        record = Model(m2m_targets=[target])
        Model.m2m_targets.delete(record, [target])

        self.assertEqual(record._changed_values, {
                'm2m_targets': {
                    'delete': [1],
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

    @with_transaction()
    def test_changed_values_reverse_field(self):
        "Test _changed_values with reverse field set"
        pool = Pool()
        Model = pool.get('test.modelview.changed_values')
        Target = pool.get('test.modelview.changed_values.target')

        record = Model(id=1)
        record.name = "Record"
        target = Target()
        target.name = "Target"
        record.targets = [target]

        self.assertEqual(record._changed_values, {
                'name': "Record",
                'targets': {
                    'add': [(0, {'id': None, 'name': "Target"})],
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
    def test_button_action(self):
        "Test button action"
        pool = Pool()
        TestModel = pool.get('test.modelview.button_action')

        action_id = TestModel.test([])

        self.assertIsInstance(action_id, int)

    @with_transaction()
    def test_button_action_return(self):
        "Test button action update value"
        pool = Pool()
        TestModel = pool.get('test.modelview.button_action')

        action = TestModel.test_update([])

        self.assertEqual(action['url'], 'http://www.tryton.org/')

    @with_transaction()
    def test_button_change(self):
        "Test button change"
        pool = Pool()
        Model = pool.get('test.modelview.button_change')

        decoder = PYSONDecoder()
        view = Model.fields_view_get()
        tree = etree.fromstring(view['arch'])
        button = tree.xpath('//button[@name="test"]')[0]

        self.assertEqual(
            set(decoder.decode(button.attrib['change'])),
            {'name', 'extra'})

    @with_transaction()
    def test_link(self):
        "Test link in view"
        pool = Pool()
        TestModel = pool.get('test.modelview.link')

        arch = TestModel.fields_view_get()['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        link, = tree.xpath('//link')

        self.assertTrue(link.attrib['id'])
        self.assertIsInstance(int(link.attrib['id']), int)

    @with_transaction()
    def test_link_without_read_access(self):
        "Test link in view without read access"
        pool = Pool()
        TestModel = pool.get('test.modelview.link')
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')

        model, = Model.search([('model', '=', 'test.modelview.link.target')])
        access = ModelAccess(model=model, group=None, perm_read=False)
        access.save()

        arch = TestModel.fields_view_get()['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        links = tree.xpath('//link')
        labels = tree.xpath('//label')

        self.assertFalse(links)
        self.assertTrue(labels)

    @unittest.skipUnless(hasattr(etree, 'RelaxNG'), "etree is missing RelaxNG")
    @with_transaction()
    def test_link_label_valid_view(self):
        "Test that replacing link by label results in a valid view"
        pool = Pool()
        TestModel = pool.get('test.modelview.link')
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        UIView = pool.get('ir.ui.view')

        model, = Model.search([('model', '=', 'test.modelview.link.target')])
        access = ModelAccess(model=model, group=None, perm_read=False)
        access.save()

        arch = TestModel.fields_view_get()['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        validator = etree.RelaxNG(etree=UIView.get_rng('form'))

        self.assertTrue(validator.validate(tree))

    @with_transaction()
    def test_link_without_action_access(self):
        "Test link in view without action access"
        pool = Pool()
        TestModel = pool.get('test.modelview.link')
        ActionWindow = pool.get('ir.action.act_window')
        Group = pool.get('res.group')
        ActionGroup = pool.get('ir.action-res.group')

        group = Group(name="Group")
        group.save()
        action_window, = ActionWindow.search(
            [('res_model', '=', 'test.modelview.link.target')])
        ActionGroup(
            action=action_window.action,
            group=group).save()

        arch = TestModel.fields_view_get()['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        links = tree.xpath('//link')
        labels = tree.xpath('//label')

        self.assertFalse(links)
        self.assertTrue(labels)

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

    @with_transaction()
    def test_depends_depends(self):
        "Test depends of depends are included"
        pool = Pool()
        DependsDepends = pool.get('test.modelview.depends_depends')

        fields = DependsDepends.fields_view_get(view_type='form')['fields']

        self.assertEqual(fields.keys(), {'foo', 'bar', 'baz'})

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

    @with_transaction()
    def test_view_attributes(self):
        "Testing view attributes are applied on view"
        pool = Pool()
        ViewAttributes = pool.get('test.modelview.view_attributes')

        arch = ViewAttributes.fields_view_get(view_type='form')['arch']
        parser = etree.XMLParser()
        tree = etree.fromstring(arch, parser=parser)
        field, = tree.xpath('//field[@name="foo"]')

        self.assertTrue(field.attrib.get('visual'))

    @with_transaction()
    def test_view_attributes_depends(self):
        "Testing view attributes depends are included on fields"
        pool = Pool()
        ViewAttributes = pool.get('test.modelview.view_attributes_depends')

        fields = ViewAttributes.fields_view_get(view_type='form')['fields']

        self.assertIn('bar', fields)


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (ModelView,):
        suite.addTests(func(testcase))
    return suite
