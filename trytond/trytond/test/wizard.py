from trytond.model import ModelView, fields
from trytond.wizard import Wizard


class TestWizardInit(ModelView):
    _name = 'test.test_wizard.init'
    name = fields.Char('Test me')

TestWizardInit()


class TestWizard(Wizard):
    _name = 'test.test_wizard'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'test.test_wizard.init',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
    }

TestWizard()
