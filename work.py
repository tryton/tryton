#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Project"

from trytond.osv import fields, OSV
import copy


class TimesheetWork(OSV):
    _name = 'timesheet.work'

    def __init__(self):
        super(TimesheetWork, self).__init__()
        self.parent = copy.copy(self.parent)
        if not self.parent._context:
            self.parent._context = "{'project_type': locals().get('project_type')}"
        else:
            self.parent._context = self.parent._context[:-1] + \
                    ",'project_type': locals().get('project_type')" + \
                    self.parent._context[-1:]
        self._reset_columns()

TimesheetWork()


class Work(OSV):
    'Work'
    _name = 'project.work'
    _description = __doc__
    _inherits = {'timesheet.work': 'work'}

    work = fields.Many2One('timesheet.work', 'Work',
            required=True)
    project_type = fields.Selection([
        ('project', 'Project'),
        ], 'Type', required=True, select=1)
    party = fields.Many2One('relationship.party', 'Party',
            states={
                'invisible': "project_type != 'project'",
            })
    party_address = fields.Many2One('relationship.address', 'Contact Address',
            domain="[('party', '=', party)]",
            states={
                'invisible': "project_type != 'project'",
            })
    comment = fields.Text('Comment')

    def default_project_type(self, cursor, user, context=None):
        return 'project'

Work()
