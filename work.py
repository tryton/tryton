# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import division

import datetime

from sql import Null
from sql.conditionals import Case

from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.pyson import Eval
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.tools import reduce_ids, grouped_slice

__all__ = ['Work']


class Work(ModelSQL, ModelView):
    'Work Effort'
    __name__ = 'project.work'
    name = fields.Char('Name', required=True, select=True)
    work = fields.Many2One('timesheet.work', 'Work', ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    type = fields.Selection([
            ('project', 'Project'),
            ('task', 'Task')
            ],
        'Type', required=True, select=True)
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
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
        fields.Boolean('Available on timesheets'),
        'on_change_with_timesheet_available')
    timesheet_duration = fields.Function(fields.TimeDelta('Duration',
            'company_work_time',
            help="Total time spent on this work and the sub-works"),
        'get_total')
    effort_duration = fields.TimeDelta('Effort', 'company_work_time',
        states={
            'invisible': Eval('type') != 'task',
            }, depends=['type'], help="Estimated Effort for this work")
    total_effort = fields.Function(fields.TimeDelta('Total Effort',
            'company_work_time',
            help="Estimated total effort for this work and the sub-works"),
        'get_total')
    progress = fields.Float('Progress',
        domain=['OR',
            ('progress', '=', None),
            [
                ('progress', '>=', 0),
                ('progress', '<=', 1),
                ],
            ],
        states={
            'invisible': Eval('type') != 'task',
            },
        depends=['type'],
        help='Estimated progress for this work')
    total_progress = fields.Function(fields.Float('Total Progress',
            digits=(16, 4),
            help='Estimated total progress for this work and the sub-works',
            states={
                'invisible': Eval('total_progress', None) == None,
                }),
        'get_total')
    comment = fields.Text('Comment')
    parent = fields.Many2One('project.work', 'Parent',
        left='left', right='right', ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)
    children = fields.One2Many('project.work', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    state = fields.Selection([
            ('opened', 'Opened'),
            ('done', 'Done'),
            ], 'State', required=True, select=True)
    sequence = fields.Integer('Sequence')

    @staticmethod
    def order_sequence(tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

    @staticmethod
    def default_type():
        return 'task'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'opened'

    @classmethod
    def default_left(cls):
        return 0

    @classmethod
    def default_right(cls):
        return 0

    @classmethod
    def __register__(cls, module_name):
        TimesheetWork = Pool().get('timesheet.work')
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table_project_work = TableHandler(cls, module_name)
        table_timesheet_work = TableHandler(TimesheetWork, module_name)
        project = cls.__table__()
        timesheet = TimesheetWork.__table__()

        migrate_sequence = (not table_project_work.column_exist('sequence')
            and table_timesheet_work.column_exist('sequence'))
        add_parent = not table_project_work.column_exist('parent')
        add_company = not table_project_work.column_exist('company')
        add_name = not table_project_work.column_exist('name')

        super(Work, cls).__register__(module_name)

        # Migration from 2.0: copy sequence from timesheet to project
        if migrate_sequence:
            cursor.execute(*timesheet.join(project,
                    condition=project.work == timesheet.id
                    ).select(timesheet.sequence, timesheet.id))
            for sequence, id_ in cursor.fetchall():
                cursor.execute(*project.update(
                        columns=[project.sequence],
                        values=[sequence],
                        where=project.work == id_))

        # Migration from 2.4: drop required on sequence
        table_project_work.not_null_action('sequence', action='remove')

        # Migration from 3.4: change effort into timedelta effort_duration
        if table_project_work.column_exist('effort'):
            cursor.execute(*project.select(project.id, project.effort,
                    where=project.effort != Null))
            for id_, effort in cursor.fetchall():
                duration = datetime.timedelta(hours=effort)
                cursor.execute(*project.update(
                        [project.effort_duration],
                        [duration],
                        where=project.id == id_))
            table_project_work.drop_column('effort')

        # Migration from 3.6: add parent, company, drop required on work,
        # fill name
        if add_parent:
            second_project = cls.__table__()
            query = project.join(timesheet,
                condition=project.work == timesheet.id
                ).join(second_project,
                    condition=timesheet.parent == second_project.work
                    ).select(project.id, second_project.id)
            cursor.execute(*query)
            for id_, parent in cursor.fetchall():
                cursor.execute(*project.update(
                        [project.parent],
                        [parent],
                        where=project.id == id_))
            cls._rebuild_tree('parent', None, 0)
        if add_company:
            cursor.execute(*project.join(timesheet,
                    condition=project.work == timesheet.id
                    ).select(project.id, timesheet.company))
            for id_, company in cursor.fetchall():
                cursor.execute(*project.update(
                        [project.company],
                        [company],
                        where=project.id == id_))
        table_project_work.not_null_action('work', action='remove')
        if add_name:
            cursor.execute(*project.join(timesheet,
                    condition=project.work == timesheet.id
                    ).select(project.id, timesheet.name))
            for id_, name in cursor.fetchall():
                cursor.execute(*project.update(
                        [project.name],
                        [name],
                        where=project.id == id_))

    @classmethod
    def __setup__(cls):
        super(Work, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('work_uniq', Unique(t, t.work),
                'There should be only one '
                'timesheet work by task/project.'),
            ]
        cls._order.insert(0, ('sequence', 'ASC'))
        cls._error_messages.update({
                'invalid_parent_state': ('Work "%(child)s" can not be opened '
                    'because its parent work "%(parent)s" is already done.'),
                'invalid_children_state': ('Work "%(parent)s" can not be '
                    'done because its child work "%(child)s" is still '
                    'opened.'),
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

    @property
    def effort_hours(self):
        if not self.effort_duration:
            return 0
        return self.effort_duration.total_seconds() / 60 / 60

    @property
    def total_effort_hours(self):
        if not self.total_effort:
            return 0
        return self.total_effort.total_seconds() / 60 / 60

    @property
    def timesheet_duration_hours(self):
        if not self.timesheet_duration:
            return 0
        return self.timesheet_duration.total_seconds() / 60 / 60

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

    @fields.depends('work')
    def on_change_with_company(self, name=None):
        return self.work.company.id if self.work else None

    @fields.depends('work')
    def on_change_with_timesheet_available(self, name=None):
        return self.work.timesheet_available if self.work else None

    @classmethod
    def sum_tree(cls, works, values, parents):
        result = values.copy()
        works = set((w.id for w in works))
        leafs = works - set(parents.itervalues())
        while leafs:
            for work in leafs:
                works.remove(work)
                parent = parents.get(work)
                if parent in result:
                    result[parent] += result[work]
            next_leafs = set(works)
            for work in works:
                parent = parents.get(work)
                if not parent:
                    continue
                if parent in next_leafs and parent in works:
                    next_leafs.remove(parent)
            leafs = next_leafs
        return result

    @classmethod
    def get_total(cls, works, names):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()

        works = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ])
        work_ids = [w.id for w in works]
        parents = {}
        for sub_ids in grouped_slice(work_ids):
            where = reduce_ids(table.id, sub_ids)
            cursor.execute(*table.select(table.id, table.parent,
                    where=where))
            parents.update(cursor.fetchall())

        if 'total_progress' in names and 'total_effort' not in names:
            names = list(names)
            names.append('total_effort')

        result = {}
        for name in names:
            values = getattr(cls, '_get_%s' % name)(works)
            result[name] = cls.sum_tree(works, values, parents)

        if 'total_progress' in names:
            digits = cls.total_progress.digits[1]
            total_progress = result['total_progress']
            total_effort = result['total_effort']
            for work in works:
                if total_effort[work.id]:
                    total_progress[work.id] = round(total_progress[work.id] /
                        (total_effort[work.id].total_seconds() / 60 / 60),
                        digits)
                else:
                    total_effort[work.id] = None
        return result

    @classmethod
    def _get_total_effort(cls, works):
        return {w.id: w.effort_duration or datetime.timedelta() for w in works}

    @classmethod
    def _get_timesheet_duration(cls, works):
        return {w.id: (w.work.duration if w.work and w.work.duration
                else datetime.timedelta())
            for w in works}

    @classmethod
    def _get_total_progress(cls, works):
        return {w.id: w.effort_hours * (w.progress or 0) for w in works}

    @classmethod
    def copy(cls, project_works, default=None):
        TimesheetWork = Pool().get('timesheet.work')

        if default is None:
            default = {}

        timesheet_default = default.copy()
        for key in timesheet_default.keys():
            if key in cls._fields:
                del timesheet_default[key]
        timesheet_default['children'] = None
        new_project_works = []
        for project_work in project_works:
            pwdefault = default.copy()
            pwdefault['children'] = None
            if project_work.work:
                timesheet_work, = TimesheetWork.copy([project_work.work],
                    default=timesheet_default)
                pwdefault['work'] = timesheet_work.id
            new_project_works.extend(super(Work, cls).copy([project_work],
                    default=pwdefault))
        return new_project_works

    @classmethod
    def delete(cls, project_works):
        TimesheetWork = Pool().get('timesheet.work')

        # Get the timesheet works linked to the project works
        timesheet_works = [pw.work for pw in project_works if pw.work]

        super(Work, cls).delete(project_works)

        if timesheet_works:
            TimesheetWork.delete(timesheet_works)

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Work, cls).search_global(text):
            icon = icon or 'tryton-project'
            yield record, rec_name, icon
