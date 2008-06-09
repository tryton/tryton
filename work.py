"Project"

from trytond.osv import fields, OSV


class Work(OSV):
    'Work'
    _name = 'project.work'
    _description = __doc__
    _inherits = {'timesheet.work': 'work'}

    work = fields.Many2One('timesheet.work', 'Work',
            required=True)
    party = fields.Many2One('relationship.party', 'Party')
    party_address = fields.Many2One('relationship.address', 'Contact Address',
            domain="[('party', '=', party)]")
    comment = fields.Text('Comment')

Work()
