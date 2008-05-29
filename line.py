"Timesheet Line"

from trytond.osv import fields, OSV
from trytond.wizard import Wizard, WizardOSV
import datetime


class Line(OSV):
    'Timesheet Line'
    _name = 'timesheet.line'
    _description = __doc__

    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=1)
    date = fields.Date('Date', required=True, select=1)
    hours = fields.Float('Hours', digits=(16, 2), required=True)
    work_type = fields.Many2One('timesheet.work_type', 'Work Type',
            required=True, select=1)
    description = fields.Char('Description')

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
            return employee_obj.name_get(cursor, user_id, employee_id,
                    context=context)[0]
        return False

    def default_date(self, cursor, user, context=None):
        if context is None:
            context = {}
        if context.get('date'):
            return context['date']
        return datetime.date.today()

Line()


class EnterLinesInit(WizardOSV):
    _name = 'timesheet.enter_lines.init'
    employee = fields.Many2One('company.employee', 'Employee')
    date = fields.Date('Date')

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
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('enter', 'Enter', 'gtk-ok', True),
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

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_line_form'),
            ('module', '=', 'timesheet'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['domain'] = str([
            ('employee', '=', data['form']['employee']),
            ('date', '=', data['form']['date']),
            ])
        res['context'] = str({
            'employee': data['form']['employee'],
            'date': data['form']['date'],
            })
        return res

EnterLines()


class HoursWorkType(OSV):
    'Hours per Work Type'
    _name = 'timesheet.hours_work_type'
    _table_query = 'SELECT DISTINCT(work_type) AS id, work_type ' \
            'FROM timesheet_line'

    work_type = fields.Many2One('timesheet.work_type', 'Work Type', select=1)
    hours = fields.Function('get_hours', digits=(16, 2), string='Hours')

    def get_hours(self, cursor, user, ids, name, arg, context=None):
        res = {}
        clause = ' '
        args = []
        for work_type_id in ids:
            res[work_type_id] = 0.0

        if context.get('start_date'):
            clause += 'AND date >= %s '
            args.append(context['start_date'])
        if context.get('end_date'):
            clause += 'AND date <= %s '
            args.append(context['end_date'])

        cursor.execute('SELECT work_type, SUM(COALESCE(hours, 0)) ' \
                'FROM timesheet_line '
                'WHERE work_type IN (' + \
                    ','.join(['%s' for x in ids]) + ') ' \
                + clause +
                'GROUP BY work_type', ids + args)
        for work_type_id, sum in cursor.fetchall():
            res[work_type_id] = sum
        return res

HoursWorkType()


class OpenHoursWorkTypeInit(WizardOSV):
    _name = 'timesheet.open_hours_work_type.init'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

OpenHoursWorkTypeInit()


class OpenHoursWorkTypes(Wizard):
    'Open Hours per Work Type'
    _name = 'timesheet.open_hours_work_type'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'timesheet.open_hours_work_type.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('open', 'Open', 'gtk-ok', True),
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

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_hours_work_type_form'),
            ('module', '=', 'timesheet'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'start_date': data['form']['start_date'],
            'end_date': data['form']['end_date'],
            })
        return res

OpenHoursWorkTypes()


class HoursEmployee(OSV):
    'Hours per Employee'
    _name = 'timesheet.hours_employee'
    _table_query = 'SELECT DISTINCT(employee) AS id, employee ' \
            'FROM timesheet_line'

    employee = fields.Many2One('company.employee', 'Employee', select=1)
    hours = fields.Function('get_hours', digits=(16, 2), string='Hours')

    def get_hours(self, cursor, user, ids, name, arg, context=None):
        res = {}
        clause = ' '
        args = []
        for employee_id in ids:
            res[employee_id] = 0.0

        if context.get('start_date'):
            clause += 'AND date >= %s '
            args.append(context['start_date'])
        if context.get('end_date'):
            clause += 'AND date <= %s '
            args.append(context['end_date'])

        cursor.execute('SELECT employee, SUM(COALESCE(hours, 0)) ' \
                'FROM timesheet_line '
                'WHERE employee IN (' + \
                    ','.join(['%s' for x in ids]) + ') ' \
                + clause +
                'GROUP BY employee', ids + args)
        for employee_id, sum in cursor.fetchall():
            res[employee_id] = sum
        return res

HoursEmployee()


class OpenHoursEmployeeInit(WizardOSV):
    _name = 'timesheet.open_hours_employee.init'
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
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('open', 'Open', 'gtk-ok', True),
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

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_hours_employee_form'),
            ('module', '=', 'timesheet'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'start_date': data['form']['start_date'],
            'end_date': data['form']['end_date'],
            })
        return res

OpenHoursEmployee()


class HoursEmployeeWorkType(OSV):
    'Hours per Employee and Work Type'
    _name = 'timesheet.hours_employee_work_type'
    _table_query = 'SELECT MAX(id) AS id, employee, work_type ' \
            'FROM timesheet_line ' \
            'GROUP BY employee, work_type'

    employee = fields.Many2One('company.employee', 'Employee', select=1)
    work_type = fields.Many2One('timesheet.work_type', 'Work Type', select=1)
    hours = fields.Function('get_hours', digits=(16, 2), string='Hours')

    def get_hours(self, cursor, user, ids, name, arg, context=None):
        res = {}
        clause = ' '
        args = []
        for obj_id in ids:
            res[obj_id] = 0.0

        if context.get('start_date'):
            clause += 'AND date >= %s '
            args.append(context['start_date'])
        if context.get('end_date'):
            clause += 'AND date <= %s '
            args.append(context['end_date'])

        cursor.execute('SELECT MAX(id), SUM(COALESCE(hours, 0)) ' \
                'FROM timesheet_line '
                'WHERE TRUE ' \
                + clause +
                'GROUP BY employee, work_type ' \
                'HAVING MAX(id) IN (' +\
                    ','.join(['%s' for x in ids]) + ')', args + ids)
        for obj_id, sum in cursor.fetchall():
            res[obj_id] = sum
        return res

HoursEmployeeWorkType()


class OpenHoursEmployeeWorkTypeInit(WizardOSV):
    _name = 'timesheet.open_hours_employee_work_type.init'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

OpenHoursEmployeeWorkTypeInit()


class OpenHoursEmployeeWorkType(Wizard):
    'Open Hours per Employee and Work Type'
    _name = 'timesheet.open_hours_employee_work_type'
    states = {
        'init': {
            'result': {
                'type': 'form',
                'object': 'timesheet.open_hours_employee_work_type.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('open', 'Open', 'gtk-ok', True),
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

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_hours_employee_work_type_form'),
            ('module', '=', 'timesheet'),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['context'] = str({
            'start_date': data['form']['start_date'],
            'end_date': data['form']['end_date'],
            })
        return res

OpenHoursEmployeeWorkType()
