# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, Workflow, fields

__all__ = [
    'WorkflowedModel',
    ]


class WorkflowedModel(Workflow, ModelSQL):
    'Workflowed Model'
    __name__ = 'test.workflowed'
    state = fields.Selection([
            ('start', 'Start'),
            ('running', 'Running'),
            ('end', 'End'),
            ], 'State')

    @classmethod
    def __setup__(cls):
        super(WorkflowedModel, cls).__setup__()
        cls._transitions |= set((
                ('start', 'running'),
                ))

    @staticmethod
    def default_state():
        return 'start'

    @classmethod
    @Workflow.transition('running')
    def run(cls, records):
        pass
