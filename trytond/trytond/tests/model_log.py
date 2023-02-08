# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.pool import Pool
from trytond.wizard import StateTransition, Wizard


class Model(Workflow, ModelSQL, ModelView):
    "Model"
    __name__ = 'test.model_log.model'

    name = fields.Char("Name")
    state = fields.Selection([
            ('start', "Start"),
            ('end', "End"),
            ], "State")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {('start', 'end')}

    @classmethod
    def default_state(cls):
        return 'start'

    @classmethod
    @ModelView.button
    def click(cls, records):
        pass

    @classmethod
    @Workflow.transition('start')
    def start(cls, records):
        pass

    @classmethod
    @Workflow.transition('end')
    def end(cls, records):
        pass


class Wizard(Wizard):
    "Wizard"
    __name__ = 'test.model_log.wizard'
    no_modification = StateTransition()
    modification = StateTransition()

    def transition_no_modification(self):
        return 'end'

    def transition_modification(self):
        self.record.name = "Bar"
        self.record.save()
        return 'end'


def register(module):
    Pool.register(
        Model,
        module=module, type_='model')
    Pool.register(
        Wizard,
        module=module, type_='wizard')
