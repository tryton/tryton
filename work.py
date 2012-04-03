#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Not, Bool, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool


class Work(ModelSQL, ModelView):
    'Work'
    _name = 'timesheet.work'
    _description = __doc__

    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active')
    parent = fields.Many2One('timesheet.work', 'Parent', left="left",
            right="right", select=True, ondelete="RESTRICT")
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    children = fields.One2Many('timesheet.work', 'parent', 'Children')
    hours = fields.Function(fields.Float('Timesheet Hours', digits=(16, 2),
        help="Total time spent on this work"), 'get_hours')
    timesheet_available = fields.Boolean('Available on timesheets',
        states={
            'readonly': Bool(Eval('timesheet_lines', [0])),
            },
        help="Allow to fill in timesheets with this work")
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    timesheet_lines = fields.One2Many('timesheet.line', 'work',
        'Timesheet Lines',
        depends=['timesheet_available', 'active'],
        states={
            'invisible': Not(Bool(Eval('timesheet_available'))),
            'readonly': Not(Bool(Eval('active'))),
            })

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

    def default_active(self):
        return True

    def default_left(self):
        return 0

    def default_right(self):
        return 0

    def default_timesheet_available(self):
        return True

    def default_company(self):
        return Transaction().context.get('company')

    def check_parent_company(self, ids):
        for work in self.browse(ids):
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

    def get_hours(self, ids, name):
        all_ids = self.search([
                ('parent', 'child_of', ids),
                ])
        # force inactive ids to be in all_ids
        all_ids = all_ids + ids
        clause = "SELECT work, sum(hours) FROM timesheet_line "\
                     "WHERE work IN (%s) "\
                     % ",".join(('%s',) * len(all_ids))
        date_cond = ""
        args = []
        if Transaction().context.get('from_date'):
            date_cond = " AND date >= %s"
            args.append(Transaction().context['from_date'])
        if Transaction().context.get('to_date'):
            date_cond += " AND date <= %s"
            args.append(Transaction().context['to_date'])
        clause += date_cond + " GROUP BY work"

        Transaction().cursor.execute(clause, all_ids + args)

        hours_by_wt = dict((i[0], i[1]) for i in
            Transaction().cursor.fetchall())
        to_compute = dict.fromkeys(all_ids, True)
        works = self.browse(all_ids)
        children = {}
        for work in works:
            if work.parent:
                children.setdefault(work.parent.id, []).append(work.id)
        self._tree_qty(hours_by_wt, children, ids, to_compute)
        return hours_by_wt

    def get_rec_name(self, ids, name):
        if not ids:
            return {}
        res = {}

        def _name(work):
            if work.parent:
                return _name(work.parent) + '\\' + work.name
            else:
                return work.name
        for work in self.browse(ids):
            res[work.id] = _name(work)
        return res

    def copy(self, ids, default=None):
        if default is None:
            default = {}
        default = default.copy()
        if 'timesheet_lines' not in default:
            default['timesheet_lines'] = None
        return super(Work, self).copy(ids, default=default)

    def write(self, ids, vals):
        child_ids = None
        if not vals.get('active', True):
            child_ids = self.search([
                ('parent', 'child_of', ids),
                ])
        res = super(Work, self).write(ids, vals)
        if child_ids:
            self.write(child_ids, {
                'active': False,
                })
        return res

Work()


class OpenWorkStart(ModelView):
    'Open Work'
    _name = 'timesheet.work.open.start'
    _description = __doc__
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')

OpenWorkStart()


class OpenWork(Wizard):
    'Open Work'
    _name = 'timesheet.work.open'

    start = StateView('timesheet.work.open.start',
        'timesheet.work_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('timesheet.act_work_hours_board')

    def do_open_(self, session, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'from_date': session.start.from_date,
                'to_date': session.start.to_date,
                })
        return action, {}

    def transition_open_(self, session):
        return 'end'

OpenWork()


class OpenWork2(OpenWork):
    _name = 'timesheet.work.open2'

    open_ = StateAction('timesheet.act_work_form2')

OpenWork2()


class OpenWorkGraph(Wizard):
    _name = 'timesheet.work.open_graph'
    start_state = 'open_'
    open_ = StateAction('timesheet.act_work_form3')

    def do_open_(self, session, action):
        pool = Pool()
        work_obj = pool.get('timesheet.work')

        if 'active_id' in Transaction().context:
            work = work_obj.browse(Transaction().context['active_id'])
            action['name'] = action['name'] + ' - ' + work.rec_name
        return action, {}

OpenWorkGraph()
