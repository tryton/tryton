# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelWorkflow, fields


class WorkflowedModel(ModelWorkflow, ModelSQL):
    _name = 'test.workflowed'

    name = fields.Char('Name')
    state = fields.Char('State')
    value = fields.Integer('Value')

    def default_transitions(self):
        return 0

    def default_value(self):
        return 0

    def workflow_start(self, workflowed):
        self.write([workflowed.id], {'state': 'Start'})

    def workflow_middle(self, workflowed):
        self.write([workflowed.id], {'state': 'Middle'})

    def workflow_end(self, workflowed):
        self.write([workflowed.id], {'state': 'End'})

    def start_middle_ok(self, workflowed):
        return workflowed.value > 4

    def middle_end_ok(self, workflowed):
        return workflowed.value < 8

WorkflowedModel()
