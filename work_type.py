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
    hours = fields.Function('get_hours', digits=(16, 2), string='Hours')
    type = fields.Selection([
        ('view', 'View'),
        ('normal', 'Normal'),
        ], 'Type', required=True, select=1)

    def __init__(self):
        super(WorkType, self).__init__()
        self._constraints += [
            ('check_recursion',
             'Error! You can not create recursive work types.', ['parent'])
        ]

    def default_active(self, cursor, user, context=None):
        return True

    def default_type(self, cursor, user, context=None):
        return 'normal'

    def get_complete_name(self, cursor, user, ids, name, arg, context=None):
        res = self.name_get(cursor, user, ids, context=context)
        return dict(res)


    def _tree_qty(self, hours_by_wt, childs, ids, to_compute):
        res = 0
        for h in ids:
            if (not childs.get(h)) or (not to_compute[h]):
                res += hours_by_wt.setdefault(h, 0)
            else:
                sub_qty = self._tree_qty(
                    hours_by_wt, childs, childs[h], to_compute)
                hours_by_wt.setdefault(h, 0)
                hours_by_wt[h] += sub_qty
                res += hours_by_wt[h]
                to_compute[h] = False
        return res

    def get_hours(self, cursor, user, ids, name, arg, context=None):
        all_ids = self.search(cursor, user, [('parent', 'child_of', ids)])
        clause = "SELECT work_type, sum(hours) FROM timesheet_line "\
                     "WHERE work_type IN (%s) "\
                     % ",".join(["%s" for id in all_ids])
        date_cond = ""
        if context.get('from_date'):
            date_cond = " AND date >= '%s'"% str(context.get('from_date'))
        if context.get('to_date'):
            date_cond += " AND date <= '%s'"% str(context.get('to_date'))
        clause += date_cond + " GROUP BY work_type"

        cursor.execute(clause, all_ids)

        hours_by_wt = dict([(i[0], i[1]) for i in cursor.fetchall()])
        to_compute = dict.fromkeys(all_ids, True)
        work_types = self.browse(cursor, user, all_ids, context=context)
        childs = {}
        for work_type in work_types:
            if work_type.parent:
                childs.setdefault(work_type.parent.id, []).append(work_type.id)
        self._tree_qty(hours_by_wt, childs, ids, to_compute)
        return hours_by_wt

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




class OpenWorkTypeInit(WizardOSV):
    _name = 'timesheet.work_type.open.init'
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
OpenWorkTypeInit()


class OpenWorkType(Wizard):
    'Open Work Types'
    _name = 'timesheet.work_type.open'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'timesheet.work_type.open.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('open', 'Open', 'gtk-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_work_type',
                'state': 'end',
            },
        },
    }

    def _action_open_work_type(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_work_type_tree2'),
            ('module', '=', 'timesheet'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'from_date': data['form']['from_date'],
            'to_date': data['form']['to_date'],
            })
        return res

OpenWorkType()
