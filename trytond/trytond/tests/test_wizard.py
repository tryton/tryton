# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import (POOL, DB_NAME, USER, CONTEXT,
    install_module)
from trytond.transaction import Transaction


class WizardTestCase(unittest.TestCase):

    def setUp(self):
        install_module('tests')
        self.wizard = POOL.get('test.test_wizard', type='wizard')
        self.session = POOL.get('ir.session.wizard')
        self.group = POOL.get('res.group')

    def test0010create(self):
        'Create Session Wizard'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            session_id, start_state, end_state = self.wizard.create()
            self.assertEqual(start_state, 'start')
            self.assertEqual(end_state, 'end')
            self.assert_(session_id)

    def test0020delete(self):
        'Delete Session Wizard'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            session_id, _, _ = self.wizard.create()
            self.wizard.delete(session_id)

    def test0030session(self):
        'Session Wizard'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            session_id, = self.session.create([{}])
            session = self.wizard(session_id)
            self.assertEqual(session.start.id, None)
            self.assertRaises(AttributeError, getattr, session.start, 'name')
            self.assertEqual(hasattr(session.start, 'name'), False)
            session.start.name = 'Test'
            self.assertRaises(AttributeError, getattr, session.start, 'user')
            self.assertEqual(hasattr(session.start, 'user'), False)
            session.start.user = USER
            group_a, = self.group.create([{
                        'name': 'Group A',
                        }])
            group_b, = self.group.create([{
                        'name': 'Group B',
                        }])
            session.start.groups = [
                group_a,
                group_b,
                ]
            session._save()
            session = self.wizard(session_id)
            self.assertEqual(session.start.id, None)
            self.assertEqual(session.start.name, 'Test')
            self.assertEqual(session.start.user.id, USER)
            self.assertEqual(session.start.user.login, 'admin')
            group_a, group_b = session.start.groups
            self.assertEqual(group_a.name, 'Group A')
            self.assertEqual(group_b.name, 'Group B')

    def test0040execute(self):
        'Execute Wizard'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            session_id, start_state, end_state = self.wizard.create()
            result = self.wizard.execute(session_id, {}, start_state)
            self.assertEqual(result.keys(), ['view'])
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
                        },
                    {
                        'state': 'next_',
                        'states': '{}',
                        'icon': 'tryton-next',
                        'default': True,
                        'string': 'Next',
                        },
                    ])
            result = self.wizard.execute(session_id, {
                    start_state: {
                        'name': 'Test Update',
                        }}, 'next_')
            self.assertEqual(len(result['actions']), 1)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(WizardTestCase)
