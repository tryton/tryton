#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Work"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV


class Work(OSV):
    'Work'
    _name = 'timesheet.work'
    _description = __doc__

    name = fields.Char('Name', required=True)
    complete_name = fields.Function('get_complete_name', type='char',
            string='Name')
    active = fields.Boolean('Active')
    parent = fields.Many2One('timesheet.work', 'Parent', select=2)
    childs = fields.One2Many('timesheet.work', 'parent', 'Childs')
    hours = fields.Function('get_hours', digits=(16, 2), string='Hours')
    type = fields.Selection([
        ('view', 'View'),
        ('normal', 'Normal'),
        ], 'Type', required=True, select=1)
    state = fields.Selection([
        ('opened', 'Opened'),
        ('closed', 'Closed'),
        ], 'State', required=True, select=1)

    def __init__(self):
        super(Work, self).__init__()
        self._constraints += [
            ('check_recursion',
             'Error! You can not create recursive works.', ['parent'])
        ]

    def default_active(self, cursor, user, context=None):
        return True

    def default_type(self, cursor, user, context=None):
        return 'normal'

    def default_state(self, cursor, user, context=None):
        return 'opened'

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
        clause = "SELECT work, sum(hours) FROM timesheet_line "\
                     "WHERE work IN (%s) "\
                     % ",".join(["%s" for id in all_ids])
        date_cond = ""
        args = []
        if context.get('from_date'):
            date_cond = " AND date >= %s"
            args.append(context['from_date'])
        if context.get('to_date'):
            date_cond += " AND date <= %s"
            args.append(context['to_date'])
        clause += date_cond + " GROUP BY work"

        cursor.execute(clause, all_ids + args)

        hours_by_wt = dict([(i[0], i[1]) for i in cursor.fetchall()])
        to_compute = dict.fromkeys(all_ids, True)
        works = self.browse(cursor, user, all_ids, context=context)
        childs = {}
        for work in works:
            if work.parent:
                childs.setdefault(work.parent.id, []).append(work.id)
        self._tree_qty(hours_by_wt, childs, ids, to_compute)
        return hours_by_wt

    def name_get(self, cursor, user, ids, context=None):
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []

        def _name(work):
            if work.parent:
                return _name(work.parent) + '\\' + work.name
            else:
                return work.name
        for work in self.browse(cursor, user, ids, context=context):
            res.append((work.id, _name(work)))
        return res

    def write(self, cursor, user, ids, vals, context=None):
        child_ids = None
        if not vals.get('active', True):
            child_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids),
                ], context=context)
        res = super(Work, self).write(cursor, user, ids, vals,
                context=context)
        if child_ids:
            self.write(cursor, user, child_ids, {
                'active': False,
                }, context=context)
        return res

Work()


class OpenWorkInit(WizardOSV):
    _name = 'timesheet.work.open.init'
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
OpenWorkInit()


class OpenWork(Wizard):
    'Open Work'
    _name = 'timesheet.work.open'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'timesheet.work.open.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_work',
                'state': 'end',
            },
        },
    }

    def _action_open_work(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_work_tree2'),
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

OpenWork()


class OpenWork2(OpenWork):
    _name = 'timesheet.work.open2'

    def _action_open_work(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_work_form2'),
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

OpenWork2()


class OpenWorkGraph(Wizard):
    _name = 'timesheet.work.open_graph'
    states = {
        'init': {
            'result': {
                'type': 'action',
                'action': '_action_open_work',
                'state': 'end',
            },
        },
    }

    def _action_open_work(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        work_obj = self.pool.get('timesheet.work')

        if context is None:
            context = {}

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_work_form3'),
            ('module', '=', 'timesheet'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        if 'active_id' in context:
            name = work_obj.name_get(cursor, user, context['active_id'],
                    context=context)[0][1]
            res['name'] = res['name'] + ' - ' + name
        return res

OpenWorkGraph()
