# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond.transaction import Transaction

__all__ = [
    'TestWizardStart', 'TestWizard',
    ]


class TestWizardStart(ModelSQL, ModelView):
    'Test Wizard'
    __name__ = 'test.test_wizard.start'
    name = fields.Char('Test me')
    user = fields.Many2One('res.user', 'User')
    groups = fields.Many2Many('res.group', None, None, 'Groups')

    @staticmethod
    def default_user():
        return Transaction().user


class TestWizard(Wizard):
    'Test Wizard'
    __name__ = 'test.test_wizard'
    start = StateView('test.test_wizard.start',
        'tests.test_wizard_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'next_', 'tryton-next', default=True),
            ])
    next_ = StateTransition()
    action = StateAction('ir.act_menu_tree')

    @staticmethod
    def default_start(fields):
        return {
            'name': 'Test wizard',
            }

    @staticmethod
    def transition_next_():
        return 'action'

    @staticmethod
    def do_action(action):
        return action, {}

    @staticmethod
    def transition_action():
        return 'end'
