# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from sql import Column, Window
from sql.aggregate import Min, Sum
from sql.conditionals import Coalesce
from sql.functions import Function, NthValue

from trytond import backend
from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import Index, ModelSQL, ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import timezone as tz
from trytond.transaction import Transaction

from .exceptions import PeriodClosedError, PeriodTransitionError


class SQLiteStrftime(Function):
    __slots__ = ()
    _function = 'STRFTIME'


class Line(ModelSQL, ModelView):
    __name__ = 'attendance.line'

    company = fields.Many2One('company.company', "Company", required=True,
        help="The company which the employee attended.")
    employee = fields.Many2One('company.employee', "Employee", required=True,
        search_context={
            'active_test': False,
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date', None)),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date', None)),
                ],
            ])
    at = fields.DateTime("At", required=True)
    date = fields.Date("Date", required=True)
    type = fields.Selection([
            ('in', 'In'),
            ('out', 'Out'),
            ], "Type", required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('at', 'DESC'))
        # Do not cache default_at
        cls.__rpc__['default_get'].cache = None

    @classmethod
    def default_at(cls):
        return dt.datetime.now()

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_employee(cls):
        return Transaction().context.get('employee')

    @fields.depends('at', 'company')
    def on_change_with_date(self):
        if not self.at:
            return
        at = self.at
        if self.company and self.company.timezone:
            timezone = tz.ZoneInfo(self.company.timezone)
            at = self.at.replace(tzinfo=tz.UTC) .astimezone(timezone)
        return at.date()

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return '%s@%s' % (self.employee.rec_name, lang.strftime(self.at))

    def compute_fields(self, field_names=None):
        cls = self.__class__
        values = super().compute_fields(field_names=field_names)
        if (not field_names
                or (cls.date.on_change_with & field_names)):
            date = self.on_change_with_date()
            if getattr(self, 'date', None) != date:
                values['date'] = date
        return values

    @classmethod
    def check_modification(cls, mode, lines, values=None, external=False):
        super().check_modification(
            mode, lines, values=values, external=external)
        if mode == 'delete':
            cls.check_closed_period(lines, msg='delete')

    @classmethod
    def validate_fields(cls, records, field_names):
        super().validate_fields(records, field_names)
        cls.check_closed_period(records, field_names=field_names)

    @classmethod
    def check_closed_period(cls, records, msg='modify', field_names=None):
        pool = Pool()
        Period = pool.get('attendance.period')
        if field_names and not (field_names & {'company', 'at'}):
            return
        for record in records:
            period_date = Period.get_last_period_date(record.company)
            if period_date and period_date > record.at:
                raise PeriodClosedError(
                    gettext('attendance.msg_%s_period_close' % msg,
                        attendance=record.rec_name,
                        period=period_date))

    @fields.depends('employee', 'at', 'id')
    def on_change_with_type(self):
        records = self.search([
                ('employee', '=', self.employee),
                ('at', '<', self.at),
                ('id', '!=', self.id),
                ],
            order=[('at', 'desc')],
            limit=1)
        if records:
            record, = records
            return {'in': 'out', 'out': 'in'}.get(record.type)
        else:
            return 'in'


class Period(Workflow, ModelSQL, ModelView):
    __name__ = 'attendance.period'
    _states = {
        'readonly': Eval('state') == 'closed',
        }

    _last_period_cache = Cache('attendance.period', context=False)

    ends_at = fields.DateTime("Ends at", required=True, states=_states)
    company = fields.Many2One('company.company', "Company", required=True,
        states=_states, help="The company the period is associated with.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ], "State", readonly=True, sort=False,
        help="The current state of the attendance period.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_indexes.add(
            Index(
                t,
                (t.company, Index.Equality()),
                (t.state, Index.Equality(cardinality='low')),
                (t.ends_at, Index.Range(order='DESC'))))
        cls._transitions |= set((
                ('draft', 'closed'),
                ('closed', 'draft'),
                ))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    'depends': ['state'],
                    },
                'close': {
                    'invisible': Eval('state') == 'closed',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    def get_rec_name(self, name):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        return lang.strftime(self.ends_at)

    @classmethod
    def get_last_period_date(cls, company):
        key = int(company)
        result = cls._last_period_cache.get(key, -1)
        if result == -1:
            records = cls.search([
                    ('company', '=', company),
                    ('state', '=', 'closed'),
                    ],
                order=[('ends_at', 'DESC')],
                limit=1)
            if records:
                record, = records
                result = record.ends_at
            else:
                result = None
            cls._last_period_cache.set(key, result)
        return result

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, periods):
        for period in periods:
            records = cls.search([
                    ('company', '=', period.company),
                    ('state', '=', 'closed'),
                    ('ends_at', '>', period.ends_at),
                    ],
                order=[('ends_at', 'ASC')],
                limit=1)
            if records:
                record, = records
                raise PeriodTransitionError(
                    gettext('attendance.msg_draft_period_previous_closed',
                        period=period.rec_name,
                        other_period=record.rec_name))
        cls._last_period_cache.clear()

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def close(cls, periods):
        for period in periods:
            records = cls.search([
                    ('company', '=', period.company),
                    ('state', '=', 'draft'),
                    ('ends_at', '<', period.ends_at),
                    ],
                order=[('ends_at', 'ASC')],
                limit=1)
            if records:
                record, = records
                raise PeriodTransitionError(
                    gettext('attendance.msg_close_period_previous_open',
                        period=period.rec_name,
                        other_period=record.rec_name))
        cls._last_period_cache.clear()


class SheetLine(ModelSQL, ModelView):
    __name__ = 'attendance.sheet.line'

    company = fields.Many2One('company.company', "Company")
    employee = fields.Many2One('company.employee', "Employee")
    from_ = fields.DateTime("From")
    to = fields.DateTime("To")
    duration = fields.TimeDelta("Duration")
    date = fields.Date("Date")
    sheet = fields.Many2One('attendance.sheet', "Sheet")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('from_', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Attendance = pool.get('attendance.line')

        attendance = Attendance.__table__()

        window = Window(
            [attendance.employee],
            order_by=[attendance.at.asc],
            frame='ROWS', start=0, end=1)
        type = NthValue(attendance.type, 1, window=window)
        from_ = NthValue(attendance.at, 1, window=window)
        to = NthValue(attendance.at, 2, window=window)
        date = NthValue(attendance.date, 1, window=window)
        query = attendance.select(
            attendance.id.as_('id'),
            attendance.company.as_('company'),
            attendance.employee.as_('employee'),
            type.as_('type'),
            from_.as_('from_'),
            to.as_('to'),
            date.as_('date'))

        sheet = (
            Min(query.id * 2, window=Window([query.employee, query.date])))

        from_ = Column(query, 'from_')
        if backend.name == 'sqlite':
            # As SQLite does not support operation on datetime
            # we convert datetime into seconds
            duration = (
                SQLiteStrftime('%s', query.to) - SQLiteStrftime('%s', from_))
        else:
            duration = query.to - from_
        return query.select(
            query.id.as_('id'),
            query.company.as_('company'),
            query.employee.as_('employee'),
            from_.as_('from_'),
            query.to.as_('to'),
            query.date.as_('date'),
            duration.as_('duration'),
            sheet.as_('sheet'),
            where=query.type == 'in')


class Sheet(ModelSQL, ModelView):
    __name__ = 'attendance.sheet'

    company = fields.Many2One('company.company', "Company")
    employee = fields.Many2One('company.employee', "Employee")
    duration = fields.TimeDelta("Duration")
    date = fields.Date("Date")
    lines = fields.One2Many('attendance.sheet.line', 'sheet', "Lines")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('attendance.sheet.line')

        line = Line.__table__()

        return line.select(
            (Min(line.id * 2)).as_('id'),
            line.company.as_('company'),
            line.employee.as_('employee'),
            Sum(line.duration).as_('duration'),
            line.date.as_('date'),
            group_by=[line.company, line.employee, line.date])


class Sheet_Timesheet(metaclass=PoolMeta):
    __name__ = 'attendance.sheet'

    timesheet_duration = fields.TimeDelta("Timesheet Duration")

    @classmethod
    def table_query(cls):
        pool = Pool()
        Timesheet = pool.get('timesheet.line')
        line = Timesheet.__table__()
        timesheet = line.select(
            Min(line.id * 2 + 1).as_('id'),
            line.company.as_('company'),
            line.employee.as_('employee'),
            Sum(line.duration).as_('duration'),
            line.date.as_('date'),
            group_by=[line.company, line.employee, line.date])
        attendance = super().table_query()
        return (attendance
            .join(
                timesheet, 'FULL' if backend.name != 'sqlite' else 'LEFT',
                condition=(attendance.company == timesheet.company)
                & (attendance.employee == timesheet.employee)
                & (attendance.date == timesheet.date))
            .select(
                Coalesce(attendance.id, timesheet.id).as_('id'),
                Coalesce(attendance.company, timesheet.company).as_('company'),
                Coalesce(
                    attendance.employee, timesheet.employee).as_('employee'),
                attendance.duration.as_('duration'),
                timesheet.duration.as_('timesheet_duration'),
                Coalesce(attendance.date, timesheet.date).as_('date'),
                ))
