#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond.transaction import Transaction


class TestWizardStart(ModelView):
    _name = 'test.test_wizard.start'
    name = fields.Char('Test me')
    user = fields.Many2One('res.user', 'User')
    groups = fields.One2Many('res.group', None, 'Groups')

    def default_user(self):
        return Transaction().user

TestWizardStart()


class TestWizard(Wizard):
    _name = 'test.test_wizard'

    start = StateView('test.test_wizard.start',
        'test.test_wizard_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'next_', 'tryton-next', default=True),
            ])
    next_ = StateTransition()
    action = StateAction('ir.act_menu_tree')

    def default_start(self, session, fields):
        return {
            'name': 'Test wizard',
            }

    def transition_next_(self, session):
        return 'action'

    def do_action(self, session, action):
        return action, {}

    def transition_action(self, session):
        return 'end'

TestWizard()
