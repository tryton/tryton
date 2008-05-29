"Work Type"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV


class WorkType(OSV):
    'Work Type'
    _name = 'timesheet.work_type'
    _description = __doc__

    name = fields.Char('Name', required=True)

WorkType()
