#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from sql import Literal
from sql.aggregate import Max, Sum
from sql.conditionals import Coalesce
from sql.functions import Extract

from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, PYSONEncoder, Date, Get
from trytond.transaction import Transaction
from trytond.pool import Pool

__all__ = ['Line', 'EnterLinesStart', 'EnterLines',
    'HoursEmployee',
    'OpenHoursEmployeeStart', 'OpenHoursEmployee',
    'HoursEmployeeWeekly', 'HoursEmployeeMonthly']


class Line(ModelSQL, ModelView):
    'Timesheet Line'
    __name__ = 'timesheet.line'
    employee = fields.Many2One('company.employee', 'Employee', required=True,
        select=True, domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ])
    date = fields.Date('Date', required=True, select=True)
    hours = fields.Float('Hours', digits=(16, 2), required=True)
    work = fields.Many2One('timesheet.work', 'Work',
        required=True, select=True, domain=[
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
        depends=['date'])
    description = fields.Char('Description')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))
        cls._sql_constraints += [
            ('check_move_hours_pos',
             'CHECK(hours >= 0.0)', 'Hours field must be positive'),
            ]

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
                ('date', '=', date),
                ])
        action['pyson_context'] = PYSONEncoder().encode({
                'employee': self.start.employee.id,
                'date': date,
                })
        action['name'] += " - " + self.start.employee.rec_name
        return action, {}

    def transition_enter(self):
        return 'end'


class HoursEmployee(ModelSQL, ModelView):
    'Hours per Employee'
    __name__ = 'timesheet.hours_employee'
    employee = fields.Many2One('company.employee', 'Employee', select=True)
    hours = fields.Float('Hours', digits=(16, 2))

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
            Sum(Coalesce(line.hours, 0)).as_('hours'),
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
    year = fields.Char('Year', select=True)
    week = fields.Integer('Week', select=True)
    employee = fields.Many2One('company.employee', 'Employee', select=True)
    hours = fields.Float('Hours', digits=(16, 2), select=True)

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
        week_column = Extract('WEEK', line.date).as_('week')
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
            Sum(Coalesce(line.hours, 0)).as_('hours'),
            group_by=(year_column, week_column, line.employee))


class HoursEmployeeMonthly(ModelSQL, ModelView):
    'Hours per Employee per Month'
    __name__ = 'timesheet.hours_employee_monthly'
    year = fields.Char('Year', select=True)
    month = fields.Integer('Month', select=True)
    employee = fields.Many2One('company.employee', 'Employee', select=True)
    hours = fields.Float('Hours', digits=(16, 2), select=True)

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
        month_column = Extract('MONTH', line.date).as_('month')
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
            Sum(Coalesce(line.hours, 0)).as_('hours'),
            group_by=(year_column, month_column, line.employee))
