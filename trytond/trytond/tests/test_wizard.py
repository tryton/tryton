# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.tests.test_tryton import (
    TestCase, activate_module, with_transaction)
from trytond.transaction import Transaction


class WizardTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        'Create Session Wizard'
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')

        session_id, start_state, end_state = Wizard.create()
        self.assertEqual(start_state, 'start')
        self.assertEqual(end_state, 'end')
        self.assertTrue(session_id)

    @with_transaction()
    def test_delete(self):
        'Delete Session Wizard'
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')

        session_id, _, _ = Wizard.create()
        Wizard.delete(session_id)

    @with_transaction()
    def test_session(self):
        'Session Wizard'
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')
        Session = pool.get('ir.session.wizard')
        Group = pool.get('res.group')
        transaction = Transaction()

        session, = Session.create([{}])
        wizard = Wizard(session.id)
        self.assertEqual(wizard.start.id, None)
        self.assertEqual(wizard.start.name, None)
        wizard.start.name = 'Test'
        self.assertEqual(wizard.start.user.id, Transaction().user)
        wizard.start.user = transaction.user
        group_a, = Group.create([{
                    'name': 'Group A',
                    }])
        group_b, = Group.create([{
                    'name': 'Group B',
                    }])
        wizard.start.groups = [
            group_a,
            group_b,
            ]
        wizard._save()
        wizard = Wizard(session.id)
        self.assertEqual(wizard.start.id, None)
        self.assertEqual(wizard.start.name, 'Test')
        self.assertEqual(wizard.start.user.id, transaction.user)
        self.assertEqual(wizard.start.user.login, 'admin')
        group_a, group_b = wizard.start.groups
        self.assertEqual(group_a.name, 'Group A')
        self.assertEqual(group_b.name, 'Group B')

    @with_transaction()
    def test_session_without_access(self):
        "Create session for wizard without access"
        pool = Pool()
        ActionWizard = pool.get('ir.action.wizard')
        Group = pool.get('res.group')
        Wizard = pool.get('test.test_wizard', type='wizard')

        group = Group(name="Test")
        group.save()
        action_wizard, = ActionWizard.search([
                ('wiz_name', '=', 'test.test_wizard'),
                ])
        action_wizard.groups = [group]
        action_wizard.save()

        with self.assertRaises(AccessError):
            session_id, start_state, end_state = Wizard.create()

    @with_transaction()
    def test_execute(self):
        'Execute Wizard'
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')

        session_id, start_state, end_state = Wizard.create()
        result = Wizard.execute(session_id, {}, start_state)
        self.assertEqual(list(result.keys()), ['view'])
        self.assertEqual(result['view']['defaults'], {
                'name': 'Test wizard',
                })
        self.assertEqual(result['view']['buttons'], [
                {
                    'state': 'end',
                    'states': '{}',
                    'icon': 'tryton-cancel',
                    'default': False,
                    'string': 'Cancel',
                    'validate': False,
                    },
                {
                    'state': 'next_',
                    'states': '{}',
                    'icon': 'tryton-next',
                    'default': True,
                    'string': 'Next',
                    'validate': True,
                    },
                ])
        result = Wizard.execute(session_id, {
                start_state: {
                    'name': 'Test Update',
                    }}, 'next_')
        self.assertEqual(len(result['actions']), 1)

    @with_transaction()
    def test_execute_without_access(self):
        "Execute wizard without access"
        pool = Pool()
        ActionWizard = pool.get('ir.action.wizard')
        Group = pool.get('res.group')
        Wizard = pool.get('test.test_wizard', type='wizard')

        session_id, start_state, end_state = Wizard.create()

        group = Group(name="Test")
        group.save()
        action_wizard, = ActionWizard.search([
                ('wiz_name', '=', 'test.test_wizard'),
                ])
        action_wizard.groups = [group]
        action_wizard.save()

        with self.assertRaises(AccessError):
            with Transaction().set_context(active_model='test.access'):
                Wizard.execute(session_id, {}, start_state)

    @with_transaction()
    def test_execute_without_model_access(self):
        "Execute wizard without model access"
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')
        ModelAccess = pool.get('ir.model.access')
        ModelAccess.create([{
                    'model': 'test.access',
                    'perm_write': False,
                    }])

        session_id, start_state, end_state = Wizard.create()

        with self.assertRaises(AccessError):
            with Transaction().set_context(active_model='test.access'):
                Wizard.execute(session_id, {}, start_state)

    @with_transaction()
    def test_execute_without_read_access(self):
        "Execute wizard without read access"
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')

        session_id, start_state, end_state = Wizard.create()

        with self.assertRaises(AccessError):
            with Transaction().set_context(
                    active_model='test.access', active_id=1):
                Wizard.execute(session_id, {}, start_state)

    @with_transaction()
    def test_execute_wrong_model(self):
        "Execute wizard on wrong model"
        pool = Pool()
        Wizard = pool.get('test.test_wizard', type='wizard')

        session_id, start_state, end_state = Wizard.create()

        with self.assertRaises(AccessError):
            with Transaction().set_context(
                    active_model='test.test_wizard.start'):
                Wizard.execute(session_id, {}, start_state)
