#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Not, Bool, Eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids

__all__ = ['Work', 'OpenWorkStart', 'OpenWork', 'OpenWork2', 'OpenWorkGraph']


class Work(ModelSQL, ModelView):
    'Work'
    __name__ = 'timesheet.work'
    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active')
    parent = fields.Many2One('timesheet.work', 'Parent', left="left",
            right="right", select=True, ondelete="RESTRICT")
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    children = fields.One2Many('timesheet.work', 'parent', 'Children')
    hours = fields.Function(fields.Float('Timesheet Hours', digits=(16, 2),
            states={
                'invisible': ~Eval('timesheet_available'),
                },
            depends=['timesheet_available'],
            help="Total time spent on this work"), 'get_hours')
    timesheet_available = fields.Boolean('Available on timesheets',
        help="Allow to fill in timesheets with this work")
    timesheet_start_date = fields.Date('Timesheet Start',
        states={
            'invisible': ~Eval('timesheet_available'),
            },
        depends=['timesheet_available'])
    timesheet_end_date = fields.Date('Timesheet End',
        states={
            'invisible': ~Eval('timesheet_available'),
            },
        depends=['timesheet_available'])
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    timesheet_lines = fields.One2Many('timesheet.line', 'work',
        'Timesheet Lines',
        depends=['timesheet_available', 'active'],
        states={
            'invisible': Not(Bool(Eval('timesheet_available'))),
            'readonly': Not(Bool(Eval('active'))),
            })

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        cls._error_messages.update({
                'invalid_parent_company': ('Every work must be in the same '
                    'company as it\'s parent work but "%(child)s" and '
                    '"%(parent)s" are in different companies.'),
                'change_timesheet_available': ('You can not unset "Available '
                    'on timesheets" for work "%s" because it already has  '
                    'timesheets.'),
                })

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    @staticmethod
    def default_timesheet_available():
        return True

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def validate(cls, works):
        super(Work, cls).validate(works)
        cls.check_recursion(works, rec_name='name')
        for work in works:
            work.check_parent_company()

    def check_parent_company(self):
        if not self.parent:
            return
        if self.parent.company != self.company:
            self.raise_user_error('invalid_parent_company', {
                    'child': self.rec_name,
                    'parent': self.parent.rec_name,
                    })

    @classmethod
    def get_hours(cls, works, name):
        pool = Pool()
        Line = pool.get('timesheet.line')
        transaction = Transaction()
        cursor = transaction.cursor
        in_max = cursor.IN_MAX
        context = transaction.context

        ids = [w.id for w in works]
        hours = dict.fromkeys(ids, 0)
        date_cond = ''
        date_args = []
        if context.get('from_date'):
            date_cond = ' AND date >= %s'
            date_args.append(context['from_date'])
        if context.get('to_date'):
            date_cond += ' AND date <= %s'
            date_args.append(context['to_date'])
        for i in range(0, len(ids), in_max):
            sub_ids = ids[i:i + in_max]
            red_sql, red_ids = reduce_ids('w.id', sub_ids)
            cursor.execute('SELECT w.id, SUM(l.hours) '
                'FROM "' + cls._table + '" AS w '
                'JOIN "' + cls._table + '" AS c '
                    'ON c.left >= w.left AND c.right <= w.right '
                'LEFT JOIN "' + Line._table + '" AS l '
                    'ON l.work = c.id '
                'WHERE ' + red_sql + ' ' + date_cond + ' '
                'GROUP BY w.id', red_ids + date_args)
            hours.update(dict(cursor.fetchall()))
        return hours

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + '\\' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split('\\')
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name.strip()))
                field = 'parent.' + field
        else:
            domain = [('name',) + tuple(clause[1:])]
        ids = [w.id for w in cls.search(domain, order=[])]
        return [('parent', 'child_of', ids)]

    @classmethod
    def copy(cls, works, default=None):
        if default is None:
            default = {}
        default = default.copy()
        if 'timesheet_lines' not in default:
            default['timesheet_lines'] = None
        return super(Work, cls).copy(works, default=default)

    @classmethod
    def write(cls, works, vals):
        pool = Pool()
        Lines = pool.get('timesheet.line')
        childs = None
        if not vals.get('timesheet_available', True):
            in_max = Transaction().cursor.IN_MAX
            for i in range(0, len(works), in_max):
                sub_ids = [w.id for w in works[i:i + in_max]]
                lines = Lines.search([('work', 'in', sub_ids)], limit=1)
                if lines:
                    cls.raise_user_error('change_timesheet_available',
                        lines[0].work.rec_name)
        if not vals.get('active', True):
            childs = cls.search([
                    ('parent', 'child_of', [w.id for w in works]),
                    ])
        super(Work, cls).write(works, vals)
        if childs:
            cls.write(childs, {
                    'active': False,
                    })


class OpenWorkStart(ModelView):
    'Open Work'
    __name__ = 'timesheet.work.open.start'
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')


class OpenWork(Wizard):
    'Open Work'
    __name__ = 'timesheet.work.open'
    start = StateView('timesheet.work.open.start',
        'timesheet.work_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('timesheet.act_work_hours_board')

    def do_open_(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'from_date': self.start.from_date,
                'to_date': self.start.to_date,
                })
        return action, {}

    def transition_open_(self):
        return 'end'


class OpenWork2(OpenWork):
    __name__ = 'timesheet.work.open2'
    open_ = StateAction('timesheet.act_work_form2')


class OpenWorkGraph(Wizard):
    __name__ = 'timesheet.work.open_graph'
    start_state = 'open_'
    open_ = StateAction('timesheet.act_work_form3')

    def do_open_(self, action):
        Work = Pool().get('timesheet.work')

        if 'active_id' in Transaction().context:
            work = Work(Transaction().context['active_id'])
            action['name'] = action['name'] + ' - ' + work.rec_name
        return action, {}
