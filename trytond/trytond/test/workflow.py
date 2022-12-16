# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, Workflow, fields


class WorkflowedModel(Workflow, ModelSQL):
    _name = 'test.workflowed'

    state = fields.Selection([
            ('start', 'Start'),
            ('running', 'Running'),
            ('end', 'End'),
            ], 'State')

    def __init__(self):
        super(WorkflowedModel, self).__init__()
        self._transitions |= set((
                ('start', 'running'),
                ))

    def default_state(self):
        return 'start'

    @Workflow.transition('running')
    def run(self, ids):
        pass

WorkflowedModel()
