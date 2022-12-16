#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.backend import FIELDS
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
            ('company', '=', Get(Eval('context', {}), 'company')),
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
            domain=[('company', '=', Get(Eval('context', {}), 'company'))])
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
        clause = ' '
        args = [True]
        if Transaction().context.get('start_date'):
            clause += 'AND date >= %s '
            args.append(Transaction().context['start_date'])
        if Transaction().context.get('end_date'):
            clause += 'AND date <= %s '
            args.append(Transaction().context['end_date'])
        return ('SELECT DISTINCT(employee) AS id, '
                'MAX(create_uid) AS create_uid, '
                'MAX(create_date) AS create_date, '
                'MAX(write_uid) AS write_uid, '
                'MAX(write_date) AS write_date, '
                'employee, '
                'SUM(COALESCE(hours, 0)) AS hours '
            'FROM timesheet_line '
            'WHERE %s '
            + clause +
            'GROUP BY employee', args)


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
        type_name = FIELDS[cls.year._type].sql_type(cls.year)[0]
        return ('SELECT id, create_uid, create_date, write_uid, write_date, '
                'CAST(year AS ' + type_name + ') AS year, week, '
                'employee, hours '
            'FROM ('
                'SELECT EXTRACT(WEEK FROM date) + '
                    'EXTRACT(YEAR FROM date) * 100 + '
                    'employee * 1000000 AS id, '
                'MAX(create_uid) AS create_uid, '
                'MAX(create_date) AS create_date, '
                'MAX(write_uid) AS write_uid, '
                'MAX(write_date) AS write_date, '
                'EXTRACT(YEAR FROM date) AS year, '
                'EXTRACT(WEEK FROM date) AS week, employee, '
                'SUM(COALESCE(hours, 0)) AS hours '
            'FROM timesheet_line '
            'GROUP BY year, week, employee) AS ' + cls._table, [])


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
        type_name = FIELDS[cls.year._type].sql_type(cls.year)[0]
        return ('SELECT id, create_uid, create_date, write_uid, write_date, '
                'CAST(year AS ' + type_name + ') AS year, month, '
                'employee, hours '
            'FROM ('
                'SELECT EXTRACT(MONTH FROM date) + '
                    'EXTRACT(YEAR FROM date) * 100 + '
                    'employee * 1000000 AS id, '
                'MAX(create_uid) AS create_uid, '
                'MAX(create_date) AS create_date, '
                'MAX(write_uid) AS write_uid, '
                'MAX(write_date) AS write_date, '
                'EXTRACT(YEAR FROM date) AS year, '
                'EXTRACT(MONTH FROM date) AS month, employee, '
                'SUM(COALESCE(hours, 0)) AS hours '
            'FROM timesheet_line '
            'GROUP BY year, month, employee) AS ' + cls._table, [])
