#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Timesheet Line"
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard
from trytond.backend import FIELDS
from trytond.pyson import Eval, PYSONEncoder, Date


class Line(ModelSQL, ModelView):
    'Timesheet Line'
    _name = 'timesheet.line'
    _description = __doc__

    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=1, domain=[('company', '=', Eval('company'))])
    date = fields.Date('Date', required=True, select=1)
    hours = fields.Float('Hours', digits=(16, 2), required=True)
    work = fields.Many2One('timesheet.work', 'Work',
            required=True, select=1, domain=[
                ('timesheet_available', '=', 'True'),
            ])
    description = fields.Char('Description')

    def __init__(self):
        super(Line, self).__init__()
        self._sql_constraints += [
            ('check_move_hours_pos',
             'CHECK(hours >= 0.0)', 'Hours field must be positive'),
            ]

    def default_employee(self, cursor, user_id, context=None):
        user_obj = self.pool.get('res.user')
        employee_obj = self.pool.get('company.employee')

        if context is None:
            context = {}
        employee_id = None
        if context.get('employee'):
            employee_id = context['employee']
        else:
            user = user_obj.browse(cursor, user_id, user_id, context=context)
            if user.employee:
                employee_id = user.employee.id
        if employee_id:
            return employee_id
        return False

    def default_date(self, cursor, user, context=None):
        date_obj = self.pool.get('ir.date')

        if context is None:
            context = {}
        if context.get('date'):
            return context['date']
        return date_obj.today(cursor, user, context=context)

    def view_header_get(self, cursor, user, value, view_type='form',
            context=None):
        if not context.get('employee'):
            return value
        employee_obj = self.pool.get('company.employee')
        employee = employee_obj.browse(cursor, user, context['employee'],
                                       context=context)
        return value + " (" + employee.name + ")"

Line()


class EnterLinesInit(ModelView):
    'Enter Lines Init'
    _name = 'timesheet.enter_lines.init'
    _description = __doc__
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            domain=[('company', '=', Eval('company'))])
    date = fields.Date('Date', required=True)

    def default_employee(self, cursor, user, context=None):
        line_obj = self.pool.get('timesheet.line')
        return line_obj.default_employee(cursor, user, context=context)

    def default_date(self, cursor, user, context=None):
        line_obj = self.pool.get('timesheet.line')
        return line_obj.default_date(cursor, user, context=context)

EnterLinesInit()


class EnterLines(Wizard):
    'Enter Lines'
    _name = 'timesheet.enter_lines'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'timesheet.enter_lines.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('enter', 'Enter', 'tryton-ok', True),
                ],
            },
        },
        'enter': {
            'result': {
                'type': 'action',
                'action': '_action_enter_lines',
                'state': 'end',
            },
        }
    }

    def _action_enter_lines(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        employee_obj = self.pool.get('company.employee')
        act_window_id = model_data_obj.get_id(cursor, user, 'timesheet',
                'act_line_form', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        date = data['form']['date']
        date = Date(date.year, date.month, date.day)
        res['pyson_domain'] = PYSONEncoder().encode([
            ('employee', '=', data['form']['employee']),
            ('date', '=', date),
            ])
        res['pyson_context'] = PYSONEncoder().encode({
            'employee': data['form']['employee'],
            'date': date,
            })

        if data['form']['employee']:
            employee = employee_obj.browse(
                cursor, user, data['form']['employee'], context=context)
            res['name'] += " - " + employee.rec_name

        return res

EnterLines()


class HoursEmployee(ModelSQL, ModelView):
    'Hours per Employee'
    _name = 'timesheet.hours_employee'
    _description = __doc__

    employee = fields.Many2One('company.employee', 'Employee', select=1)
    hours = fields.Float('Hours', digits=(16, 2))

    def table_query(self, context=None):
        if context is None:
            context = {}
        clause = ' '
        args = [True]
        if context.get('start_date'):
            clause += 'AND date >= %s '
            args.append(context['start_date'])
        if context.get('end_date'):
            clause += 'AND date <= %s '
            args.append(context['end_date'])
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


class OpenHoursEmployeeInit(ModelView):
    'Open Hours Employee Init'
    _name = 'timesheet.open_hours_employee.init'
    _description = __doc__
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

OpenHoursEmployeeInit()


class OpenHoursEmployee(Wizard):
    'Open Hours per Employee'
    _name = 'timesheet.open_hours_employee'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'timesheet.open_hours_employee.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('open', 'Open', 'tryton-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open',
                'state': 'end',
            },
        },
    }

    def _action_open(self, cursor, user, data, context=None):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')
        act_window_id = model_data_obj.get_id(cursor, user, 'timesheet',
                'act_hours_employee_form', context=context)
        res = act_window_obj.read(cursor, user, act_window_id, context=context)
        res['pyson_context'] = PYSONEncoder().encode({
            'start_date': data['form']['start_date'],
            'end_date': data['form']['end_date'],
            })
        return res

OpenHoursEmployee()


class HoursEmployeeWeekly(ModelSQL, ModelView):
    'Hours per Employee per Week'
    _name = 'timesheet.hours_employee_weekly'
    _description = __doc__

    year = fields.Char('Year', select=1)
    week = fields.Integer('Week', select=1)
    employee = fields.Many2One('company.employee', 'Employee', select=1)
    hours = fields.Float('Hours', digits=(16, 2), select=1)

    def __init__(self):
        super(HoursEmployeeWeekly, self).__init__()
        self._order.insert(0, ('year', 'DESC'))
        self._order.insert(1, ('week', 'DESC'))
        self._order.insert(2, ('employee', 'ASC'))

    def table_query(self, context=None):
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

    year = fields.Char('Year', select=1)
    month = fields.Integer('Month', select=1)
    employee = fields.Many2One('company.employee', 'Employee', select=1)
    hours = fields.Float('Hours', digits=(16, 2), select=1)

    def __init__(self):
        super(HoursEmployeeMonthly, self).__init__()
        self._order.insert(0, ('year', 'DESC'))
        self._order.insert(1, ('month', 'DESC'))
        self._order.insert(2, ('employee', 'ASC'))

    def table_query(self, context=None):
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
