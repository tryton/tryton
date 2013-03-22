#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval
from trytond.backend import TableHandler
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Work']


class Work(ModelSQL, ModelView):
    'Work Effort'
    __name__ = 'project.work'
    _rec_name = 'work'
    work = fields.Many2One('timesheet.work', 'Work', required=True,
            ondelete='CASCADE')
    active = fields.Function(fields.Boolean('Active'),
        'get_active', setter='set_active', searcher='search_active')
    type = fields.Selection([
            ('project', 'Project'),
            ('task', 'Task')
            ],
        'Type', required=True, select=True)
    company = fields.Function(fields.Many2One('company.company', 'Company'),
        'get_company', searcher='search_comany')
    party = fields.Many2One('party.party', 'Party',
        states={
            'invisible': Eval('type') != 'project',
            }, depends=['type'])
    party_address = fields.Many2One('party.address', 'Contact Address',
        domain=[('party', '=', Eval('party'))],
        states={
            'invisible': Eval('type') != 'project',
            }, depends=['party', 'type'])
    timesheet_available = fields.Function(
        fields.Boolean('Available on timesheets'), 'get_timesheet_available')
    hours = fields.Function(fields.Float('Timesheet Hours', digits=(16, 2),
            states={
                'invisible': ~Eval('timesheet_available'),
                },
            depends=['timesheet_available'],
            help="Total time spent on this work"), 'get_hours')
    effort = fields.Float("Effort",
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type'], help="Estimated Effort for this work")
    total_effort = fields.Function(fields.Float('Total Effort',
        help="Estimated total effort for this work and the sub-works"),
        'get_total_effort')
    comment = fields.Text('Comment')
    parent = fields.Function(fields.Many2One('project.work', 'Parent'),
            'get_parent', setter='set_parent', searcher='search_parent')
    children = fields.One2Many('project.work', 'parent', 'Children')
    state = fields.Selection([
            ('opened', 'Opened'),
            ('done', 'Done'),
            ], 'State', required=True, select=True)
    sequence = fields.Integer('Sequence',
        order_field='(%(table)s.sequence IS NULL) %(order)s, '
        '%(table)s.sequence %(order)s')

    @staticmethod
    def default_type():
        return 'task'

    @staticmethod
    def default_state():
        return 'opened'

    @staticmethod
    def default_effort():
        return 0.0

    @classmethod
    def __register__(cls, module_name):
        TimesheetWork = Pool().get('timesheet.work')
        cursor = Transaction().cursor
        table_project_work = TableHandler(cursor, cls, module_name)
        table_timesheet_work = TableHandler(cursor, TimesheetWork, module_name)
        migrate_sequence = (not table_project_work.column_exist('sequence')
            and table_timesheet_work.column_exist('sequence'))

        super(Work, cls).__register__(module_name)

        # Migration from 2.0: copy sequence from timesheet to project
        if migrate_sequence:
            cursor.execute(
                'SELECT t.sequence, t.id '
                'FROM "%s" AS t '
                'JOIN "%s" AS p ON (p.work = t.id)' % (
                    TimesheetWork._table, cls._table))
            for sequence, id_ in cursor.fetchall():
                sql = ('UPDATE "%s" '
                    'SET sequence = %%s '
                    'WHERE work = %%s' % cls._table)
                cursor.execute(sql, (sequence, id_))

        # Migration from 2.4: drop required on sequence
        table_project_work.not_null_action('sequence', action='remove')

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        cls._sql_constraints += [
            ('work_uniq', 'UNIQUE(work)', 'There should be only one '
                'timesheet work by task/project.'),
            ]
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'invalid_parent_state': ('Work "%(child)s" can not be opened '
                    'because its parent work "%(parent)s" is already done."'),
                'invalid_children_state': ('Work "%(parent)s" can not be '
                    'done because its child work "%(child)s" is still '
                    'opened."'),
                })

    @classmethod
    def validate(cls, works):
        super(Work, cls).validate(works)
        for work in works:
            work.check_state()

    def check_state(self):
        if (self.state == 'opened'
                and (self.parent and self.parent.state == 'done')):
            self.raise_user_error('invalid_parent_state', {
                    'child': self.rec_name,
                    'parent': self.parent.rec_name,
                    })
        if self.state == 'done':
            for child in self.children:
                if child.state == 'opened':
                    self.raise_user_error('invalid_children_state', {
                            'parent': self.rec_name,
                            'child': child.rec_name,
                            })

    def get_rec_name(self, name):
        return self.work.name

    @staticmethod
    def default_active():
        return True

    def get_active(self, name):
        return self.work.active

    @classmethod
    def set_active(self, works, name, value):
        pool = Pool()
        Work = pool.get('timesheet.work')

        Work.write([p.work for p in works], {
                'active': value,
                })

    @classmethod
    def search_active(cls, name, clause):
        return [('work.active',) + tuple(clause[1:])]

    def get_company(self, name):
        return self.work.company.id

    @classmethod
    def search_comany(cls, name, clause):
        return [('work.company',) + tuple(clause[1:])]

    def get_timesheet_available(self, name):
        return self.work.timesheet_available

    def get_hours(self, name):
        return self.work.hours

    @classmethod
    def get_parent(cls, project_works, name):
        parents = dict.fromkeys([w.id for w in project_works], None)

        # ptw2pw is "parent timesheet work to project works":
        ptw2pw = {}
        for project_work in project_works:
            if not project_work.work.parent:
                continue
            if project_work.work.parent.id in ptw2pw:
                ptw2pw[project_work.work.parent.id].append(project_work.id)
            else:
                ptw2pw[project_work.work.parent.id] = [project_work.id]

        with Transaction().set_context(active_test=False):
            parent_projects = cls.search([
                    ('work', 'in', ptw2pw.keys()),
                    ])
        for parent_project in parent_projects:
            if parent_project.work.id in ptw2pw:
                child_projects = ptw2pw[parent_project.work.id]
                for child_project in child_projects:
                    parents[child_project] = parent_project.id

        return parents

    @classmethod
    def set_parent(cls, project_works, name, value):
        TimesheetWork = Pool().get('timesheet.work')
        if value:
            project_works.append(cls(value))
            child_timesheet_works = [x.work for x in project_works[:-1]]
            parent_timesheet_work_id = project_works[-1].work.id
        else:
            child_timesheet_works = [x.work for x in project_works]
            parent_timesheet_work_id = None

        TimesheetWork.write(child_timesheet_works, {
                'parent': parent_timesheet_work_id
                })

    @classmethod
    def search_parent(cls, name, domain):
        TimesheetWork = Pool().get('timesheet.work')

        project_work_domain = []
        timesheet_work_domain = []
        if domain[0].startswith('parent.'):
            project_work_domain.append(
                    (domain[0].replace('parent.', ''),)
                    + domain[1:])
        elif domain[0] == 'parent':
            timesheet_work_domain.append(domain)

        # ids timesheet_work_domain in operand are project_work ids,
        # we need to convert them to timesheet_work ids
        operands = set()
        for _, _, operand in timesheet_work_domain:
            if (isinstance(operand, (int, long))
                    and not isinstance(operand, bool)):
                operands.add(operand)
            elif isinstance(operand, list):
                for o in operand:
                    if isinstance(o, (int, long)) and not isinstance(o, bool):
                        operands.add(o)
        pw2tw = {}
        if operands:
            operands = list(operands)
            # filter out non-existing ids:
            operands = cls.search([
                    ('id', 'in', operands)
                    ])
            # create project_work > timesheet_work mapping
            for pw in operands:
                pw2tw[pw.id] = pw.work.id

            for i, d in enumerate(timesheet_work_domain):
                if isinstance(d[2], (int, long)):
                    new_d2 = pw2tw.get(d[2], 0)
                elif isinstance(d[2], list):
                    new_d2 = []
                    for item in d[2]:
                        item = pw2tw.get(item, 0)
                        new_d2.append(item)
                timesheet_work_domain[i] = (d[0], d[1], new_d2)

        if project_work_domain:
            project_works = cls.search(project_work_domain)
            timesheet_work_domain.append(
                ('id', 'in', [pw.work.id for pw in project_works]))

        tw_ids = [tw.id for tw in TimesheetWork.search(timesheet_work_domain)]

        return [('work', 'in', tw_ids)]

    @staticmethod
    def sum_tree(works, getter):
        leafs = set()
        result = {}
        for work in works:
            if not work.children:
                leafs.add(work)
            result[work.id] = getter(work)

        works = set(works)
        while leafs:
            for work in leafs:
                works.remove(work)
                if work.parent and work.parent.id in result:
                    result[work.parent.id] += result[work.id]
            next_leafs = set(w for w in works)
            for work in works:
                if not work.parent:
                    continue
                if work.parent.id in next_leafs and work.parent in works:
                    next_leafs.remove(work.parent)
            leafs = next_leafs
        return result

    @classmethod
    def get_total_effort(cls, works, name):

        works = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ('active', '=', True),
                ]) + works
        return cls.sum_tree(works, lambda w: w.effort or 0)

    @classmethod
    def copy(cls, project_works, default=None):
        TimesheetWork = Pool().get('timesheet.work')

        if default is None:
            default = {}

        timesheet_default = default.copy()
        for key in timesheet_default.keys():
            if key in cls._fields:
                del timesheet_default[key]
        new_project_works = []
        for project_work in project_works:
            timesheet_work, = TimesheetWork.copy([project_work.work],
                default=timesheet_default)
            pwdefault = default.copy()
            pwdefault['work'] = timesheet_work.id
            new_project_works.extend(super(Work, cls).copy([project_work],
                    default=pwdefault))
        return new_project_works

    @classmethod
    def delete(cls, project_works):
        TimesheetWork = Pool().get('timesheet.work')

        # Get the timesheet works linked to the project works
        timesheet_works = [pw.work for pw in project_works]

        super(Work, cls).delete(project_works)

        TimesheetWork.delete(timesheet_works)
