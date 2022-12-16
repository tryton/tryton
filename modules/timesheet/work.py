#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Work"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.pyson import PYSONEncoder


class Work(ModelSQL, ModelView):
    'Work'
    _name = 'timesheet.work'
    _description = __doc__

    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active')
    parent = fields.Many2One('timesheet.work', 'Parent', left="left",
            right="right", select=2, ondelete="RESTRICT")
    left = fields.Integer('Left', required=True, select=1)
    right = fields.Integer('Right', required=True, select=1)
    children = fields.One2Many('timesheet.work', 'parent', 'Children')
    hours = fields.Function(fields.Float('Timesheet Hours', digits=(16, 2),
        help="Total time spent on this work"), 'get_hours')
    timesheet_available = fields.Boolean('Available on timesheets',
            help="Allow to fill in timesheets with this work")
    company = fields.Many2One('company.company', 'Company', required=True)

    def __init__(self):
        super(Work, self).__init__()
        self._constraints += [
            ('check_recursion', 'recursive_works'),
            ('check_parent_company', 'parent_company'),
        ]
        self._error_messages.update({
            'recursive_works': 'You can not create recursive works!',
            'parent_company': 'Every work must be in the same company '\
                'as it\'s parent work!',
        })

    def default_active(self, cursor, user, context=None):
        return True

    def default_timesheet_available(self, cursor, user, context=None):
        return True

    def default_company(self, cursor, user, context=None):
        if context is None:
            context = {}
        if context.get('company'):
            return context['company']
        return False

    def check_parent_company(self, cursor, user, ids):
        for work in self.browse(cursor, user, ids):
            if not work.parent:
                continue
            if work.parent.company.id != work.company.id:
                return False
        return True

    def _tree_qty(self, hours_by_wt, children, ids, to_compute):
        res = 0
        for h in ids:
            if (not children.get(h)) or (not to_compute[h]):
                res += hours_by_wt.setdefault(h, 0)
            else:
                sub_qty = self._tree_qty(
                    hours_by_wt, children, children[h], to_compute)
                hours_by_wt.setdefault(h, 0)
                hours_by_wt[h] += sub_qty
                res += hours_by_wt[h]
                to_compute[h] = False
        return res

    def get_hours(self, cursor, user, ids, name, context=None):
        all_ids = self.search(cursor, user, [
                ('parent', 'child_of', ids)
                ], context=context)
        # force inactive ids to be in all_ids
        all_ids = list(set(all_ids + ids))
        clause = "SELECT work, sum(hours) FROM timesheet_line "\
                     "WHERE work IN (%s) "\
                     % ",".join(('%s',) * len(all_ids))
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
        children = {}
        for work in works:
            if work.parent:
                children.setdefault(work.parent.id, []).append(work.id)
        self._tree_qty(hours_by_wt, children, ids, to_compute)
        return hours_by_wt

    def get_rec_name(self, cursor, user, ids, name, context=None):
        if not ids:
            return {}
        res = {}
        def _name(work):
            if work.parent:
                return _name(work.parent) + '\\' + work.name
            else:
                return work.name
        for work in self.browse(cursor, user, ids, context=context):
            res[work.id] = _name(work)
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


class OpenWorkInit(ModelView):
    'Open Work Init'
    _name = 'timesheet.work.open.init'
    _description = __doc__
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
        act_window_id = model_data_obj.get_id(cursor, user, 'timesheet',
                'act_work_tree2', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        res['pyson_context'] = PYSONEncoder().encode({
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
        act_window_id = model_data_obj.get_id(cursor, user, 'timesheet',
                'act_work_form2', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        res['pyson_context'] = PYSONEncoder().encode({
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

        act_window_id = model_data_obj.get_id(cursor, user, 'timesheet',
                'act_work_form3', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        if 'active_id' in context:
            work = work_obj.browse(cursor, user, context['active_id'],
                    context=context)
            res['name'] = res['name'] + ' - ' + work.rec_name
        return res

OpenWorkGraph()
