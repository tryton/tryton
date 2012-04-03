#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.backend import FIELDS
from trytond.pyson import Eval, PYSONEncoder, Date, Get
from trytond.transaction import Transaction
from trytond.pool import Pool


class Line(ModelSQL, ModelView):
    'Timesheet Line'
    _name = 'timesheet.line'
    _description = __doc__

    employee = fields.Many2One('company.employee', 'Employee', required=True,
        select=True, domain=[
            ('company', '=', Get(Eval('context', {}), 'company')),
            ])
    date = fields.Date('Date', required=True, select=True)
    hours = fields.Float('Hours', digits=(16, 2), required=True)
    work = fields.Many2One('timesheet.work', 'Work',
            required=True, select=True, domain=[
                ('timesheet_available', '=', 'True'),
            ])
    description = fields.Char('Description')

    def __init__(self):
        super(Line, self).__init__()
        self._sql_constraints += [
            ('check_move_hours_pos',
             'CHECK(hours >= 0.0)', 'Hours field must be positive'),
            ]

    def default_employee(self):
        user_obj = Pool().get('res.user')
        employee_id = None
        if Transaction().context.get('employee'):
            employee_id = Transaction().context['employee']
        else:
            user = user_obj.browse(Transaction().user)
            if user.employee:
                employee_id = user.employee.id
        if employee_id:
            return employee_id

    def default_date(self):
        date_obj = Pool().get('ir.date')

        return Transaction().context.get('date') or date_obj.today()

    def view_header_get(self, value, view_type='form'):
        if not Transaction().context.get('employee'):
            return value
        employee_obj = Pool().get('company.employee')
        employee = employee_obj.browse(Transaction().context['employee'])
        return value + " (" + employee.name + ")"

Line()


class EnterLinesStart(ModelView):
    'Enter Lines'
    _name = 'timesheet.line.enter.start'
    _description = __doc__
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            domain=[('company', '=', Get(Eval('context', {}), 'company'))])
    date = fields.Date('Date', required=True)

    def default_employee(self):
        line_obj = Pool().get('timesheet.line')
        return line_obj.default_employee()

    def default_date(self):
        line_obj = Pool().get('timesheet.line')
        return line_obj.default_date()

EnterLinesStart()


class EnterLines(Wizard):
    'Enter Lines'
    _name = 'timesheet.line.enter'

    start = StateView('timesheet.line.enter.start',
        'timesheet.line_enter_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Enter', 'enter', 'tryton-ok', default=True),
            ])
    enter = StateAction('timesheet.act_line_form')

    def do_enter(self, session, action):
        date = session.start.date
        date = Date(date.year, date.month, date.day)
        action['pyson_domain'] = PYSONEncoder().encode([
                ('employee', '=', session.start.employee.id),
                ('date', '=', date),
                ])
        action['pyson_context'] = PYSONEncoder().encode({
                'employee': session.start.employee.id,
                'date': date,
                })
        action['name'] += " - " + session.start.employee.rec_name
        return action, {}

    def transition_enter(self, session):
        return 'end'

EnterLines()


class HoursEmployee(ModelSQL, ModelView):
    'Hours per Employee'
    _name = 'timesheet.hours_employee'
    _description = __doc__

    employee = fields.Many2One('company.employee', 'Employee', select=True)
    hours = fields.Float('Hours', digits=(16, 2))

    def table_query(self):
        clause = ' '
        args = [True]
        if Transaction().context.get('start_date'):
            clause += 'AND date >= %s '
            args.append(Transaction().context['start_date'])
        if Transaction().context.get('end_date'):
            clause += 'AND date <= %s '
            args.append(Transaction().context['end_date'])
        return ('SELECT DISTINCT(employee) AS id, ' \
                    'MAX(create_uid) AS create_uid, ' \
                    'MAX(create_date) AS create_date, ' \
                    'MAX(write_uid) AS write_uid, ' \
                    'MAX(write_date) AS write_date, ' \
                    'employee, ' \
                    'SUM(COALESCE(hours, 0)) AS hours ' \
                'FROM timesheet_line ' \
                'WHERE %s ' \
                + clause + \
                'GROUP BY employee', args)

HoursEmployee()


class OpenHoursEmployeeStart(ModelView):
    'Open Hours per Employee'
    _name = 'timesheet.hours_employee.open.start'
    _description = __doc__
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

OpenHoursEmployeeStart()


class OpenHoursEmployee(Wizard):
    'Open Hours per Employee'
    _name = 'timesheet.hours_employee.open'

    start = StateView('timesheet.hours_employee.open.start',
        'timesheet.hours_employee_open_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Open', 'open_', 'tryton-ok', default=True),
            ])
    open_ = StateAction('timesheet.act_hours_employee_form')

    def do_open_(self, session, action):
        action['pyson_context'] = PYSONEncoder().encode({
                'start_date': session.start.start_date,
                'end_date': session.start.end_date,
                })
        return action, {}

    def transition_open_(self, session):
        return 'end'

OpenHoursEmployee()


class HoursEmployeeWeekly(ModelSQL, ModelView):
    'Hours per Employee per Week'
    _name = 'timesheet.hours_employee_weekly'
    _description = __doc__

    year = fields.Char('Year', select=True)
    week = fields.Integer('Week', select=True)
    employee = fields.Many2One('company.employee', 'Employee', select=True)
    hours = fields.Float('Hours', digits=(16, 2), select=True)

    def __init__(self):
        super(HoursEmployeeWeekly, self).__init__()
        self._order.insert(0, ('year', 'DESC'))
        self._order.insert(1, ('week', 'DESC'))
        self._order.insert(2, ('employee', 'ASC'))

    def table_query(self):
        type_name = FIELDS[self.year._type].sql_type(self.year)[0]
        return ('SELECT id, create_uid, create_date, write_uid, write_date, ' \
                    'CAST(year AS ' + type_name + ') AS year, week, ' \
                    'employee, hours ' \
                    'FROM ('
                        'SELECT EXTRACT(WEEK FROM date) + ' \
                            'EXTRACT(YEAR FROM date) * 100 + ' \
                            'employee * 1000000 AS id, ' \
                        'MAX(create_uid) AS create_uid, ' \
                        'MAX(create_date) AS create_date, ' \
                        'MAX(write_uid) AS write_uid, ' \
                        'MAX(write_date) AS write_date, ' \
                        'EXTRACT(YEAR FROM date) AS year, ' \
                        'EXTRACT(WEEK FROM date) AS week, employee, ' \
                        'SUM(COALESCE(hours, 0)) AS hours ' \
                    'FROM timesheet_line ' \
                    'GROUP BY year, week, employee) AS ' + self._table, [])

HoursEmployeeWeekly()


class HoursEmployeeMonthly(ModelSQL, ModelView):
    'Hours per Employee per Month'
    _name = 'timesheet.hours_employee_monthly'
    _description = __doc__

    year = fields.Char('Year', select=True)
    month = fields.Integer('Month', select=True)
    employee = fields.Many2One('company.employee', 'Employee', select=True)
    hours = fields.Float('Hours', digits=(16, 2), select=True)

    def __init__(self):
        super(HoursEmployeeMonthly, self).__init__()
        self._order.insert(0, ('year', 'DESC'))
        self._order.insert(1, ('month', 'DESC'))
        self._order.insert(2, ('employee', 'ASC'))

    def table_query(self):
        type_name = FIELDS[self.year._type].sql_type(self.year)[0]
        return ('SELECT id, create_uid, create_date, write_uid, write_date, ' \
                    'CAST(year AS ' + type_name + ') AS year, month, ' \
                    'employee, hours ' \
                    'FROM ('
                        'SELECT EXTRACT(MONTH FROM date) + ' \
                            'EXTRACT(YEAR FROM date) * 100 + ' \
                            'employee * 1000000 AS id, ' \
                        'MAX(create_uid) AS create_uid, ' \
                        'MAX(create_date) AS create_date, ' \
                        'MAX(write_uid) AS write_uid, ' \
                        'MAX(write_date) AS write_date, ' \
                        'EXTRACT(YEAR FROM date) AS year, ' \
                        'EXTRACT(MONTH FROM date) AS month, employee, ' \
                        'SUM(COALESCE(hours, 0)) AS hours ' \
                    'FROM timesheet_line ' \
                    'GROUP BY year, month, employee) AS ' + self._table, [])

HoursEmployeeMonthly()
