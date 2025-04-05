# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from collections import defaultdict

from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSQL, ModelView, fields, sequence_ordered,
    sum_tree, tree)
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, If, PYSONEncoder, TimeDelta
from trytond.transaction import Transaction

from .exceptions import WorkProgressValidationError


class WorkStatus(DeactivableMixin, sequence_ordered(), ModelSQL, ModelView):
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
    def on_modification(cls, mode, records, field_names=None):
        super().on_modification(mode, records, field_names=field_names)
        cls._get_default_status_cache.clear()
        cls._get_window_domains_cache.clear()

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
    __name__ = 'project.work'
    name = fields.Char("Name", required=True)
    type = fields.Selection([
            ('project', 'Project'),
            ('task', 'Task')
            ],
        "Type", required=True)
    company = fields.Many2One('company.company', "Company", required=True)
    party = fields.Many2One('party.party', 'Party',
        states={
            'invisible': Eval('type') != 'project',
            },
        context={
            'company': Eval('company', -1),
            },
        depends={'company'})
    party_address = fields.Many2One('party.address', 'Contact Address',
        domain=[('party', '=', Eval('party', -1))],
        states={
            'invisible': Eval('type') != 'project',
            })
    timesheet_works = fields.One2Many(
        'timesheet.work', 'origin', 'Timesheet Works', readonly=True, size=1)
    timesheet_available = fields.Function(fields.Boolean(
            "Available on timesheets",
            help="Check to record time spent."),
        'get_timesheet_available', setter='set_timesheet_available')
    timesheet_start_date = fields.Function(fields.Date('Timesheet Start',
            states={
                'invisible': ~Eval('timesheet_available'),
                }),
        'get_timesheet_date', setter='set_timesheet_date')
    timesheet_end_date = fields.Function(fields.Date('Timesheet End',
            states={
                'invisible': ~Eval('timesheet_available'),
                }),
        'get_timesheet_date', setter='set_timesheet_date')
    timesheet_duration = fields.Function(fields.TimeDelta('Duration',
            'company_work_time',
            help="Total time spent on this work and the sub-works."),
        'get_total')
    effort_duration = fields.TimeDelta(
        "Effort", 'company_work_time',
        domain=['OR',
            ('effort_duration', '=', None),
            ('effort_duration', '>=', TimeDelta()),
            ],
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
            digits=(None, 4),
            help='Estimated total progress for this work and the sub-works.',
            states={
                'invisible': (
                    Eval('total_progress', None) == None),  # noqa: E711
                }),
        'get_total')
    comment = fields.Text('Comment')
    parent = fields.Many2One(
        'project.work', 'Parent', path='path', ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    path = fields.Char("Path")
    children = fields.One2Many('project.work', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])
    status = fields.Many2One(
        'project.work.status', "Status", required=True,
        domain=[If(Bool(Eval('type')), ('types', 'in', Eval('type')), ())])

    @classmethod
    def __setup__(cls):
        cls.path.search_unaccented = False
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.update({
                Index(t, (t.path, Index.Similarity(begin=True))),
                })

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
    def __register__(cls, module_name):
        table_project_work = cls.__table_handler__(module_name)

        super().__register__(module_name)

        # Migration from 6.0: remove left and right
        table_project_work.drop_column('left')
        table_project_work.drop_column('right')

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
        index = super().index_set_field(name)
        if name in {'timesheet_start_date', 'timesheet_end_date'}:
            index = cls.index_set_field('timesheet_available') + 1
        return index

    @classmethod
    def validate(cls, works):
        super().validate(works)
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
    def get_total(cls, works, names):
        works = cls.search([
                ('parent', 'child_of', [w.id for w in works]),
                ])

        if 'total_progress' in names and 'total_effort' not in names:
            names = list(names)
            names.append('total_effort')

        result = {}
        for name in names:
            values = getattr(cls, '_get_%s' % name)(works)
            result[name] = sum_tree(works, values)

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
        return defaultdict(
            datetime.timedelta,
            {w.id: w.effort_duration or datetime.timedelta() for w in works})

    @classmethod
    def _get_timesheet_duration(cls, works):
        durations = defaultdict(datetime.timedelta)
        for work in works:
            value = datetime.timedelta()
            for timesheet_work in work.timesheet_works:
                if timesheet_work.duration:
                    value += timesheet_work.duration
            durations[work.id] = value
        return durations

    @classmethod
    def _get_total_progress(cls, works):
        return defaultdict(
            int,
            {w.id: w.effort_hours * (w.progress or 0) for w in works})

    @classmethod
    def copy(cls, project_works, default=None):
        pool = Pool()
        WorkStatus = pool.get('project.work.status')
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('progress', None)
        default.setdefault(
            'status', lambda data: WorkStatus.get_default_status(data['type']))
        new_works = super().copy(project_works, default=default)
        to_save = []
        for work, new_work in zip(project_works, new_works):
            if work.timesheet_available:
                new_work.timesheet_available = work.timesheet_available
                new_work.timesheet_start_date = work.timesheet_start_date
                new_work.timesheet_end_date = work.timesheet_end_date
                to_save.append(new_work)
        if to_save:
            cls.save(to_save)
        return new_works

    @classmethod
    def on_delete(cls, project_works):
        pool = Pool()
        TimesheetWork = pool.get('timesheet.work')
        callback = super().on_delete(project_works)
        timesheet_works = {
            w for pw in project_works for w in pw.timesheet_works}
        if timesheet_works:
            timesheet_works = TimesheetWork.browse(timesheet_works)
            callback.append(lambda: TimesheetWork.delete(timesheet_works))
        return callback

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super().search_global(text):
            icon = icon or 'tryton-project'
            yield record, rec_name, icon
