"Work Type"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV


class WorkType(OSV):
    'Work Type'
    _name = 'timesheet.work_type'
    _description = __doc__

    name = fields.Char('Name', required=True)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Name')
    active = fields.Boolean('Active')
    parent = fields.Many2One('timesheet.work_type', 'Parent', select=2)
    childs = fields.One2Many('timesheet.work_type', 'parent', 'Childs')
    type = fields.Selection([
        ('view', 'View'),
        ('normal', 'Normal'),
        ], 'Type', required=True, select=1)

    def default_active(self, cursor, user, context=None):
        return True

    def default_type(self, cursor, user, context=None):
        return 'normal'

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        def _name(work_type):
            if work_type.parent:
                return _name(work_type.parent) + '\\' + work_type.name
            else:
                return work_type.name
        for work_type in self.browse(cursor, user, ids, context=context):
            res.append((work_type.id, _name(work_type)))
        return res

    def write(self, cursor, user, ids, vals, context=None):
        child_ids = None
        if not vals.get('active', True):
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ], context=context)
        res = super(WorkType, self).write(cursor, user, ids, vals,
                context=context)
        if child_ids:
            self.write(cursor, user, child_ids, {
                'active': False,
                }, context=context)
        return res

WorkType()
