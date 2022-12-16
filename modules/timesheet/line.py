# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import division
import datetime

from sql import Literal
from sql.aggregate import Max, Sum
from sql.functions import Extract, CharLength

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

__all__ = ['Line', 'EnterLinesStart', 'EnterLines',
    'HoursEmployee',
    'OpenHoursEmployeeStart', 'OpenHoursEmployee',
    'HoursEmployeeWeekly', 'HoursEmployeeMonthly']


class Line(ModelSQL, ModelView):
    'Timesheet Line'
    __name__ = 'timesheet.line'
    company = fields.Many2One('company.company', 'Company', required=True)
    employee = fields.Many2One('company.employee', 'Employee', required=True,
        select=True, domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    date = fields.Date('Date', required=True, select=True)
    duration = fields.TimeDelta('Duration', 'company_work_time', required=True)
    work = fields.Many2One('timesheet.work', 'Work',
        required=True, select=True, domain=[
            ('company', '=', Eval('company', -1)),
            ('timesheet_available', '=', True),
            ['OR',
                ('timesheet_start_date', '=', None),
                ('timesheet_start_date', '<=', Eval('date')),
                ],
            ['OR',
                ('timesheet_end_date', '=', None),
                ('timesheet_end_date', '>=', Eval('date')),
                ],
            ],
        depends=['date', 'company'])
    description = fields.Char('Description')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._error_messages.update({
                'duration_positive': (
                    'Duration of line "%(line)s" must be positive.'),
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        table = TableHandler(cls, module_name)
        sql_table = cls.__table__()
        pool = Pool()
        Work = pool.get('timesheet.work')
        work = Work.__table__()

        created_company = not table.column_exist('company')

        super(Line, cls).__register__(module_name)

        # Migration from 3.4: new company field
        if created_company:
            # Don't use FROM because SQLite nor MySQL support it.
            cursor.execute(*sql_table.update(
                    [sql_table.company], [work.select(work.company,
                            where=work.id == sql_table.work)]))
        # Migration from 3.4: change hours into timedelta duration
        if table.column_exist('hours'):
            table.drop_constraint('check_move_hours_pos')
            cursor.execute(*sql_table.select(
                    sql_table.id, sql_table.hours))
            for id_, hours in cursor.fetchall():
                duration = datetime.timedelta(hours=hours)
                cursor.execute(*sql_table.update(
                        [sql_table.duration],
                        [duration],
                        where=sql_table.id == id_))
            table.drop_column('hours')

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_employee():
        User = Pool().get('res.user')
        employee_id = None
        if Transaction().context.get('employee'):
            employee_id = Transaction().context['employee']
        else:
            user = User(Transaction().user)
            if user.employee:
                employee_id = user.employee.id
        if employee_id:
            return employee_id

    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Transaction().context.get('date') or Date_.today()

    @classmethod
    def view_header_get(cls, value, view_type='form'):
        if not Transaction().context.get('employee'):
            return value
        Employee = Pool().get('company.employee')
        employee = Employee(Transaction().context['employee'])
        return value + " (" + employee.rec_name + ")"

    @classmethod
    def validate(cls, lines):
        super(Line, cls).validate(lines)
        for line in lines:
            line.check_duration()

    def check_duration(self):
        if self.duration < datetime.timedelta():
            self.raise_user_error('duration_positive', {
                    'line': self.rec_name,
                    })

    @property
    def hours(self):
        return self.duration.total_seconds() / 60 / 60


class EnterLinesStart(ModelView):
    'Enter Lines'
    __name__ = 'timesheet.line.enter.start'
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            domain=[('company', '=', Eval('context', {}).get('company', -1))])
    date = fields.Date('Date', required=True)

    @staticmethod
    def default_employee():
        Line = Pool().get('timesheet.line')
        return Line.default_employee()

    @staticmethod
    def default_date():
        Line = Pool().get('timesheet.line')
        return Line.default_date()


class EnterLines(Wizard):
    'Enter Lines'
    __name__ = 'timesheet.line.enter'
    start = StateView('timesheet.line.enter.start',
        'timesheet.line_enter_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Enter', 'enter', 'tryton-ok', default=True),
            ])
    enter = StateAction('timesheet.act_line_form')

    def do_enter(self, action):
        date = self.start.date
        date = Date(date.year, date.month, date.day)
        action['pyson_domain'] = PYSONEncoder().encode([
                ('employee', '=', self.start.employee.id),
                ('company', '=', self.start.employee.company.id),
                ('date', '=', date),
                ])
        action['pyson_context'] = PYSONEncoder().encode({
                'employee': self.start.employee.id,
                'company': self.start.employee.company.id,
                'date': date,
                })
        action['name'] += " - " + self.start.employee.rec_name
        return action, {}

    def transition_enter(self):
        return 'end'


class HoursEmployee(ModelSQL, ModelView):
    'Hours per Employee'
    __name__ = 'timesheet.hours_employee'
    employee = fields.Many2One('company.employee', 'Employee')
    duration = fields.TimeDelta('Duration', 'company_work_time')

    @staticmethod
    def table_query():
        pool = Pool()
        Line = pool.get('timesheet.line')
        line = Line.__table__()
        where = Literal(True)
        if Transaction().context.get('start_date'):
            where &= line.date >= Transaction().context['start_date']
        if Transaction().context.get('end_date'):
            where &= line.date <= Transaction().context['end_date']
        return line.select(
            line.employee.as_('id'),
            Max(line.create_uid).as_('create_uid'),
            Max(line.create_date).as_('create_date'),
            Max(line.write_uid).as_('write_uid'),
            Max(line.write_date).as_('write_date'),
            line.employee,
            Sum(line.duration).as_('duration'),
            where=where,
            group_by=line.employee)


class OpenHoursEmployeeStart(ModelView):
    'Open Hours per Employee'
    __name__ = 'timesheet.hours_employee.open.start'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


class OpenHoursEmployee(Wizard):
    'Open Hours per Employee'
    __name__ = 'timesheet.hours_employee.open'
    start = StateView('timesheet.hours_employee.open.start',
        'timesheet.hours_employee_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('timesheet.act_hours_employee_form')

    def do_open_(self, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': self.start.start_date,
                'end_date': self.start.end_date,
                })
        return action, {}

    def transition_open_(self):
        return 'end'


class HoursEmployeeWeekly(ModelSQL, ModelView):
    'Hours per Employee per Week'
    __name__ = 'timesheet.hours_employee_weekly'
    year = fields.Char('Year')
    week_internal = fields.Char('Week')
    week = fields.Function(fields.Char('Week'),
        'get_week', searcher='search_week')
    employee = fields.Many2One('company.employee', 'Employee')
    duration = fields.TimeDelta('Duration', 'company_work_time')

    @classmethod
    def __setup__(cls):
        super(HoursEmployeeWeekly, cls).__setup__()
        cls._order.insert(0, ('year', 'DESC'))
        cls._order.insert(1, ('week', 'DESC'))
        cls._order.insert(2, ('employee', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('timesheet.line')
        line = Line.__table__()
        type_name = cls.year.sql_type().base
        year_column = Extract('YEAR', line.date).cast(type_name).as_('year')
        type_name = cls.week_internal.sql_type().base
        week_column = Extract('WEEK', line.date).cast(type_name).as_(
            'week_internal')
        return line.select(
            Max(Extract('WEEK', line.date)
                + Extract('YEAR', line.date) * 100
                + line.employee * 1000000).as_('id'),
            Max(line.create_uid).as_('create_uid'),
            Max(line.create_date).as_('create_date'),
            Max(line.write_uid).as_('write_uid'),
            Max(line.write_date).as_('write_date'),
            year_column,
            week_column,
            line.employee,
            Sum(line.duration).as_('duration'),
            group_by=(year_column, week_column, line.employee))

    def get_week(self, name):
        return '%02i' % int(self.week_internal)

    @classmethod
    def search_week(self, name, domain):
        return [('week_internal',) + tuple(domain[1:])]

    @classmethod
    def order_week(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.week_internal), table.week_internal]


class HoursEmployeeMonthly(ModelSQL, ModelView):
    'Hours per Employee per Month'
    __name__ = 'timesheet.hours_employee_monthly'
    year = fields.Char('Year')
    month_internal = fields.Char('Month')
    month = fields.Function(fields.Char('Month'),
        'get_month', searcher='search_month')
    employee = fields.Many2One('company.employee', 'Employee')
    duration = fields.TimeDelta('Duration', 'company_work_time')

    @classmethod
    def __setup__(cls):
        super(HoursEmployeeMonthly, cls).__setup__()
        cls._order.insert(0, ('year', 'DESC'))
        cls._order.insert(1, ('month', 'DESC'))
        cls._order.insert(2, ('employee', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('timesheet.line')
        line = Line.__table__()
        type_name = cls.year.sql_type().base
        year_column = Extract('YEAR', line.date).cast(type_name).as_('year')
        type_name = cls.month_internal.sql_type().base
        month_column = Extract('MONTH', line.date).cast(type_name).as_(
            'month_internal')
        return line.select(
            Max(Extract('MONTH', line.date)
                + Extract('YEAR', line.date) * 100
                + line.employee * 1000000).as_('id'),
            Max(line.create_uid).as_('create_uid'),
            Max(line.create_date).as_('create_date'),
            Max(line.write_uid).as_('write_uid'),
            Max(line.write_date).as_('write_date'),
            year_column,
            month_column,
            line.employee,
            Sum(line.duration).as_('duration'),
            group_by=(year_column, month_column, line.employee))

    def get_month(self, name):
        return '%02i' % int(self.month_internal)

    @classmethod
    def search_month(self, name, domain):
        return [('month_internal',) + tuple(domain[1:])]

    @classmethod
    def order_month(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.month_internal), table.month_internal]
