# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from sql import Null

from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    ModelView, ModelSQL, fields, sequence_ordered, tree, DeactivableMixin)
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval, If, Bool, PYSONEncoder
from trytond.tools import reduce_ids, grouped_slice

from .exceptions import WorkProgressValidationError


class WorkStatus(DeactivableMixin, sequence_ordered(), ModelSQL, ModelView):
    'Work Status'
    __name__ = 'project.work.status'

    _get_default_status_cache = Cache('project_work_status.get_default_status')
    _get_window_domains_cache = Cache('project_work_status.get_window_domains')

    types = fields.MultiSelection(
        'get_types', "Types",
        help="The type of works which can use this status.")
    name = fields.Char("Name", required=True, translate=True)
    progress = fields.Float(
        "Progress",
        domain=['OR',
            ('progress', '=', None),
            [
                ('progress', '>=', 0),
                ('progress', '<=', 1),
                ],
            ],
        help="The minimum progress required for this status.")
    default = fields.Boolean(
        "Default",
        help="Check to use as default status for the type.")
    count = fields.Boolean(
        "Count",
        help="Check to show the number of works in this status.")

    @classmethod
    def get_types(cls):
        pool = Pool()
        Work = pool.get('project.work')
        return Work.fields_get(['type'])['type']['selection']

    @classmethod
    def get_default_status(cls, type_=None):
        if type_ is None:
            return None
        status = cls._get_default_status_cache.get(type_, -1)
        if status != -1:
            return status
        records = cls.search([
                ('types', 'in', type_),
                ('default', '=', True)
                ], limit=1)
        if records:
            status = records[0].id
        else:
            status = None
        cls._get_default_status_cache.set(type, status)
        return status

    @classmethod
    def create(cls, vlist):
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()

    @classmethod
    def delete(cls, status):
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()
        super().delete(status)

    @classmethod
    def get_window_domains(cls, action):
        pool = Pool()
        Data = pool.get('ir.model.data')
        if action.id == Data.get_id('project', 'act_project_tree'):
            return cls._get_window_domains([x[0] for x in cls.get_types()])
        elif action.id == Data.get_id('project', 'act_project_form'):
            return cls._get_window_domains(['project'])
        elif action.id == Data.get_id('project', 'act_task_form'):
            return cls._get_window_domains(['task'])
        else:
            return []

    @classmethod
    def _get_window_domains(cls, types):
        key = tuple(sorted(types))
        domains = cls._get_window_domains_cache.get(key)
        if domains is not None:
            return domains
        encoder = PYSONEncoder()
        domains = []
        for status in cls.search([('types', 'in', types)]):
            domain = encoder.encode([('status', '=', status.id)])
            domains.append((status.name, domain, status.count))
        if domains:
            domains.append(
                (gettext('project.msg_domain_all'), '[]', False))
        cls._get_window_domains_cache.set(key, domains)
        return domains


class Work(sequence_ordered(), tree(separator='\\'), ModelSQL, ModelView):
    'Work Effort'
    __name__ = 'project.work'
    name = fields.Char('Name', required=True, select=True)
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
    timesheet_works = fields.One2Many(
        'timesheet.work', 'origin', 'Timesheet Works', readonly=True, size=1)
    timesheet_available = fields.Function(
        fields.Boolean('Available on timesheets'),
        'get_timesheet_available', setter='set_timesheet_available')
    timesheet_start_date = fields.Function(fields.Date('Timesheet Start',
            states={
                'invisible': ~Eval('timesheet_available'),
                },
            depends=['timesheet_available']),
        'get_timesheet_date', setter='set_timesheet_date')
    timesheet_end_date = fields.Function(fields.Date('Timesheet End',
            states={
                'invisible': ~Eval('timesheet_available'),
                },
            depends=['timesheet_available']),
        'get_timesheet_date', setter='set_timesheet_date')
    timesheet_duration = fields.Function(fields.TimeDelta('Duration',
            'company_work_time',
            help="Total time spent on this work and the sub-works."),
        'get_total')
    effort_duration = fields.TimeDelta('Effort', 'company_work_time',
        help="Estimated Effort for this work.")
    total_effort = fields.Function(fields.TimeDelta('Total Effort',
            'company_work_time',
            help="Estimated total effort for this work and the sub-works."),
        'get_total')
    progress = fields.Float('Progress',
        domain=['OR',
            ('progress', '=', None),
            [
                ('progress', '>=', 0),
                ('progress', '<=', 1),
                ],
            ],
        help='Estimated progress for this work.')
    total_progress = fields.Function(fields.Float('Total Progress',
            digits=(16, 4),
            help='Estimated total progress for this work and the sub-works.',
            states={
                'invisible': (
                    Eval('total_progress', None) == None),  # noqa: E711
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
    status = fields.Many2One(
        'project.work.status', "Status", required=True, select=True,
        domain=[If(Bool(Eval('type')), ('types', 'in', Eval('type')), ())],
        depends=['type'])

    @staticmethod
    def default_type():
        return 'task'

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_status(cls):
        pool = Pool()
        WorkStatus = pool.get('project.work.status')
        return WorkStatus.get_default_status(cls.default_type())

    @classmethod
    def default_left(cls):
        return 0

    @classmethod
    def default_right(cls):
        return 0

    @classmethod
    def __register__(cls, module_name):
        TimesheetWork = Pool().get('timesheet.work')
        cursor = Transaction().connection.cursor()
        table_project_work = cls.__table_handler__(module_name)
        project = cls.__table__()
        timesheet = TimesheetWork.__table__()

        work_exist = table_project_work.column_exist('work')
        add_parent = (not table_project_work.column_exist('parent')
            and work_exist)
        add_company = (not table_project_work.column_exist('company')
            and work_exist)
        add_name = (not table_project_work.column_exist('name')
            and work_exist)

        super(Work, cls).__register__(module_name)

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

        # Migration from 4.0: remove work
        if work_exist:
            table_project_work.drop_constraint('work_uniq')
            update = Transaction().connection.cursor()
            cursor.execute(*project.select(project.id, project.work,
                    where=project.work != Null))
            for project_id, work_id in cursor:
                update.execute(*timesheet.update(
                        [timesheet.origin, timesheet.name],
                        ['%s,%s' % (cls.__name__, project_id), Null],
                        where=timesheet.id == work_id))
            table_project_work.drop_column('work')

        # Migration from 5.4: replace state by status
        table_project_work.not_null_action('state', action='remove')

    @fields.depends('type', 'status')
    def on_change_type(self):
        pool = Pool()
        WorkState = pool.get('project.work.status')
        if (self.type
                and (not self.status
                    or self.type not in self.status.types)):
            self.status = WorkState.get_default_status(self.type)

    @fields.depends('status', 'progress')
    def on_change_status(self):
        if (self.status
                and self.status.progress is not None
                and self.status.progress > (self.progress or -1.0)):
            self.progress = self.status.progress

    @classmethod
    def index_set_field(cls, name):
        index = super(Work, cls).index_set_field(name)
        if name in {'timesheet_start_date', 'timesheet_end_date'}:
            index = cls.index_set_field('timesheet_available') + 1
        return index

    @classmethod
    def validate(cls, works):
        super(Work, cls).validate(works)
        for work in works:
            work.check_work_progress()

    def check_work_progress(self):
        pool = Pool()
        progress = -1 if self.progress is None else self.progress
        if (self.status.progress is not None
                and progress < self.status.progress):
            Lang = pool.get('ir.lang')
            lang = Lang.get()
            raise WorkProgressValidationError(
                gettext('project.msg_work_invalid_progress_status',
                    work=self.rec_name,
                    progress=lang.format('%.2f%%', self.status.progress * 100),
                    status=self.status.rec_name))
        if (self.status.progress == 1.0
                and not all(c.progress == 1.0 for c in self.children)):
            raise WorkProgressValidationError(
                gettext('project.msg_work_children_progress',
                    work=self.rec_name,
                    status=self.status.rec_name))
        if (self.parent
                and self.parent.progress == 1.0
                and not self.progress == 1.0):
            raise WorkProgressValidationError(
                gettext('project.msg_work_parent_progress',
                    work=self.rec_name,
                    parent=self.parent.rec_name))

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

    @classmethod
    def default_timesheet_available(cls):
        return False

    def get_timesheet_available(self, name):
        return bool(self.timesheet_works)

    @classmethod
    def set_timesheet_available(cls, projects, name, value):
        pool = Pool()
        Timesheet = pool.get('timesheet.work')

        to_create = []
        to_delete = []
        for project in projects:
            if not project.timesheet_works and value:
                to_create.append({
                        'origin': str(project),
                        'company': project.company.id,
                        })
            elif project.timesheet_works and not value:
                to_delete.extend(project.timesheet_works)

        if to_create:
            Timesheet.create(to_create)
        if to_delete:
            Timesheet.delete(to_delete)

    def get_timesheet_date(self, name):
        if self.timesheet_works:
            func = {
                'timesheet_start_date': min,
                'timesheet_end_date': max,
                }[name]
            return func(getattr(w, name) for w in self.timesheet_works)

    @classmethod
    def set_timesheet_date(cls, projects, name, value):
        pool = Pool()
        Timesheet = pool.get('timesheet.work')
        timesheets = [w for p in projects for w in p.timesheet_works]
        if timesheets:
            Timesheet.write(timesheets, {
                    name: value,
                    })

    @classmethod
    def sum_tree(cls, works, values, parents):
        result = values.copy()
        works = set((w.id for w in works))
        leafs = works - set(parents.values())
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
                    total_progress[work.id] = round(total_progress[work.id]
                        / (total_effort[work.id].total_seconds() / 60 / 60),
                        digits)
                else:
                    total_effort[work.id] = None
        return result

    @classmethod
    def _get_total_effort(cls, works):
        return {w.id: w.effort_duration or datetime.timedelta() for w in works}

    @classmethod
    def _get_timesheet_duration(cls, works):
        durations = {}
        for work in works:
            value = datetime.timedelta()
            for timesheet_work in work.timesheet_works:
                if timesheet_work.duration:
                    value += timesheet_work.duration
            durations[work.id] = value
        return durations

    @classmethod
    def _get_total_progress(cls, works):
        return {w.id: w.effort_hours * (w.progress or 0) for w in works}

    @classmethod
    def copy(cls, project_works, default=None):
        pool = Pool()
        WorkStatus = pool.get('project.work.status')
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('children', None)
        default.setdefault('progress', None)
        default.setdefault(
            'status', lambda data: WorkStatus.get_default_status(data['type']))
        return super().copy(project_works, default=default)

    @classmethod
    def delete(cls, project_works):
        TimesheetWork = Pool().get('timesheet.work')

        # Get the timesheet works linked to the project works
        timesheet_works = [
            w for pw in project_works for w in pw.timesheet_works]

        super(Work, cls).delete(project_works)

        if timesheet_works:
            with Transaction().set_context(_check_access=False):
                TimesheetWork.delete(timesheet_works)

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(Work, cls).search_global(text):
            icon = icon or 'tryton-project'
            yield record, rec_name, icon
