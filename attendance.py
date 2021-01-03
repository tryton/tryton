# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import copy
import datetime as dt
from collections import defaultdict
from itertools import chain

try:
    import pytz
except ImportError:
    pytz = None

from sql import Window, Literal, Null, Column
from sql.aggregate import Min, Sum
from sql.conditionals import Coalesce
from sql.functions import NthValue, CurrentTimestamp, Function

from trytond import backend
from trytond.cache import Cache
from trytond.i18n import gettext
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from .exceptions import PeriodClosedError, PeriodTransitionError


class SQLiteStrftime(Function):
    __slots__ = ()
    _function = 'STRFTIME'


class Line(ModelSQL, ModelView):
    "Attendance Line"
    __name__ = 'attendance.line'

    company = fields.Many2One('company.company', "Company", required=True,
        help="The company which the employee attended.")
    employee = fields.Many2One('company.employee', "Employee", required=True,
        domain=[
            ('company', '=', Eval('company')),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date')),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date')),
                ],
            ],
        depends=['company', 'date'])
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
        if pytz and self.company and self.company.timezone:
            timezone = pytz.timezone(self.company.timezone)
            at = pytz.utc.localize(self.at, is_dst=None).astimezone(timezone)
        return at.date()

    def get_rec_name(self, name):
        return '%s@%s' % (self.employee.rec_name, self.at)

    @classmethod
    def create(cls, vlist):
        lines = super().create(vlist)
        to_write = defaultdict(list)
        for line in lines:
            date = line.on_change_with_date()
            if line.date != date:
                to_write[date].append(line)
        if to_write:
            cls.write(*chain([l, {'date': d}] for d, l in to_write.items()))
        return lines

    @classmethod
    def write(cls, *args):
        super().write(*args)

        to_write = defaultdict(list)
        actions = iter(args)
        for lines, values in zip(actions, actions):
            for line in lines:
                date = line.on_change_with_date()
                if line.date != date:
                    to_write[date].append(line)
        if to_write:
            cls.write(*chain([l, {'date': d}] for d, l in to_write.items()))

    @classmethod
    def delete(cls, records):
        cls.check_closed_period(records, msg='delete')
        super().delete(records)

    @classmethod
    def validate(cls, records):
        super().validate(records)
        cls.check_closed_period(records)

    @classmethod
    def check_closed_period(cls, records, msg='modify'):
        pool = Pool()
        Period = pool.get('attendance.period')
        for record in records:
            period_date = Period.get_last_period_date(record.company)
            if period_date and period_date > record.at:
                raise PeriodClosedError(
                    gettext('attendance.msg_%s_period_close' % msg,
                        attendance=record.rec_name,
                        period=period_date))

    @fields.depends('employee', 'at')
    def on_change_with_type(self):
        records = self.search([
                ('employee', '=', self.employee),
                ('at', '<', self.at),
                ],
            order=[('at', 'desc')],
            limit=1)
        if records:
            record, = records
            return {'in': 'out', 'out': 'in'}.get(record.type)
        else:
            return 'in'


class Period(Workflow, ModelSQL, ModelView):
    "Attendance Period"
    __name__ = 'attendance.period'
    _states = {
        'readonly': Eval('state') == 'closed',
        }
    _depends = ['state']

    _last_period_cache = Cache('attendance.period', context=False)

    ends_at = fields.DateTime("Ends at", required=True, states=_states,
        depends=_depends)
    company = fields.Many2One('company.company', "Company", required=True,
        states=_states, depends=_depends,
        help="The company the period is associated with.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('closed', 'Closed'),
        ], 'State', select=True, readonly=True,
        help="The current state of the attendance period.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
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
        return str(self.date)

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
    "Attendance SheetLine"
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

        transaction = Transaction()
        database = transaction.database

        attendance = Attendance.__table__()

        if database.has_window_functions():
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
        else:
            next_attendance = Attendance.__table__()
            to = next_attendance.select(
                next_attendance.at,
                where=(next_attendance.employee == attendance.employee)
                & (next_attendance.at > attendance.at),
                order_by=[next_attendance.at.asc],
                limit=1)
            query = attendance.select(
                attendance.id.as_('id'),
                attendance.company.as_('company'),
                attendance.employee.as_('employee'),
                attendance.type.as_('type'),
                attendance.at.as_('from_'),
                to.as_('to'),
                attendance.date.as_('date'))

            query2 = copy.copy(query)
            sheet = query2.select(
                Min(query2.id * 2),
                where=(query2.employee == query.employee)
                & (query2.date == query.date))

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
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            query.company.as_('company'),
            query.employee.as_('employee'),
            from_.as_('from_'),
            query.to.as_('to'),
            query.date.as_('date'),
            duration.as_('duration'),
            sheet.as_('sheet'),
            where=query.type == 'in')


class Sheet(ModelSQL, ModelView):
    "Attendance Sheet"
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
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
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
                Literal(0).as_('create_uid'),
                CurrentTimestamp().as_('create_date'),
                cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
                cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
                Coalesce(attendance.company, timesheet.company).as_('company'),
                Coalesce(
                    attendance.employee, timesheet.employee).as_('employee'),
                attendance.duration.as_('duration'),
                timesheet.duration.as_('timesheet_duration'),
                Coalesce(attendance.date, timesheet.date).as_('date'),
                ))
