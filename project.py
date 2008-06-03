"Project"

from trytond.osv import fields, OSV


class Project(OSV):
    'Project'
    _name = 'project.project'
    _description = __doc__
    _inherits = {'timesheet.work_type': 'work_type'}

    work_type = fields.Many2One('timesheet.work_type', 'Work Type',
            required=True)
    party = fields.Many2One('relationship.party', 'Party')
    party_address = fields.Many2One('relationship.address', 'Contact Address',
            domain="[('party', '=', party)]")
    comment = fields.Text('Comment')

Project()
