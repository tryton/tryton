# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime

from sql import Literal
from sql.aggregate import Max, Sum
from sql.functions import Extract, CharLength

from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval, PYSONEncoder, Date
from trytond.transaction import Transaction
from trytond.pool import Pool

from .exceptions import DurationValidationError


class Line(ModelSQL, ModelView):
    'Timesheet Line'
    __name__ = 'timesheet.line'
    company = fields.Many2One('company.company', 'Company', required=True,
        help="The company on which the time is spent.")
    employee = fields.Many2One('company.employee', 'Employee', required=True,
        select=True, domain=[
            ('company', '=', Eval('company', -1)),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date')),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date')),
                ],
            ],
        depends=['company', 'date'],
        help="The employee who spends the time.")
    date = fields.Date('Date', required=True, select=True,
        help="When the time is spent.")
    duration = fields.TimeDelta('Duration', 'company_work_time', required=True)
    work = fields.Many2One('timesheet.work', 'Work',
        required=True, select=True, domain=[
            ('company', '=', Eval('company', -1)),
            ['OR',
                ('timesheet_start_date', '=', None),
                ('timesheet_start_date', '<=', Eval('date')),
                ],
            ['OR',
                ('timesheet_end_date', '=', None),
                ('timesheet_end_date', '>=', Eval('date')),
                ],
            ],
        depends=['date', 'company'],
        help="The work on which the time is spent.")
    description = fields.Char('Description',
        help="Additional description of the work done.")
    uuid = fields.Char("UUID", readonly=True)

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('uuid_unique', Unique(t, t.uuid),
                'timesheet.msg_line_uuid_unique'),
            ]
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().connection.cursor()
        table = cls.__table_handler__(module_name)
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
    def validate(cls, lines):
        super(Line, cls).validate(lines)
        for line in lines:
            line.check_duration()

    def check_duration(self):
        if self.duration < datetime.timedelta():
            raise DurationValidationError(
                gettext('timesheet.msg_line_duration_positive',
                    line=self.rec_name))

    @classmethod
    def copy(cls, lines, default=None):
        if default is not None:
            default = default.copy()
        else:
            default = {}
        default.setdefault('uuid')
        return super().copy(lines, default=default)

    @property
    def hours(self):
        return self.duration.total_seconds() / 60 / 60

    def to_json(self):
        return {
            'id': self.id,
            'work': self.work.id,
            'work.name': self.work.rec_name,
            'duration': self.duration.total_seconds(),
            'description': self.description,
            'uuid': self.uuid,
            }


class EnterLinesStart(ModelView):
    'Enter Lines'
    __name__ = 'timesheet.line.enter.start'
    employee = fields.Many2One('company.employee', 'Employee', required=True,
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', Eval('date')),
                ],
            ['OR',
                ('end_date', '=', None),
                ('end_date', '>=', Eval('date')),
                ],
            ],
        depends=['date'],
        help="The employee who spends the time.")
    date = fields.Date('Date', required=True,
        help="When the time is spent.")

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
        pool = Pool()
        Lang = pool.get('ir.lang')
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
        action['name'] += ' @ %(date)s - %(employee)s' % {
            'date': Lang.get().strftime(self.start.date),
            'employee': self.start.employee.rec_name,
            }
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


class HoursEmployeeContext(ModelView):
    'Hours per Employee Context'
    __name__ = 'timesheet.hours_employee.context'
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


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
    def search_week(cls, name, domain):
        return [('week_internal',) + tuple(domain[1:])]

    @classmethod
    def order_week(cls, tables):
        table, _ = tables[None]
        return [CharLength(table.week_internal), table.week_internal]


class HoursEmployeeMonthly(ModelSQL, ModelView):
    'Hours per Employee per Month'
    __name__ = 'timesheet.hours_employee_monthly'
    year = fields.Char('Year')
    month = fields.Many2One('ir.calendar.month', "Month")
    employee = fields.Many2One('company.employee', 'Employee')
    duration = fields.TimeDelta('Duration', 'company_work_time')

    @classmethod
    def __setup__(cls):
        super(HoursEmployeeMonthly, cls).__setup__()
        cls._order.insert(0, ('year', 'DESC'))
        cls._order.insert(1, ('month.index', 'DESC'))
        cls._order.insert(2, ('employee', 'ASC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        Line = pool.get('timesheet.line')
        Month = pool.get('ir.calendar.month')
        line = Line.__table__()
        month = Month.__table__()
        type_name = cls.year.sql_type().base
        year_column = Extract('YEAR', line.date).cast(type_name).as_('year')
        month_index = Extract('MONTH', line.date)
        return line.join(month, condition=month_index == month.id).select(
            Max(Extract('MONTH', line.date)
                + Extract('YEAR', line.date) * 100
                + line.employee * 1000000).as_('id'),
            Max(line.create_uid).as_('create_uid'),
            Max(line.create_date).as_('create_date'),
            Max(line.write_uid).as_('write_uid'),
            Max(line.write_date).as_('write_date'),
            year_column,
            month.id.as_('month'),
            line.employee,
            Sum(line.duration).as_('duration'),
            group_by=(year_column, month.id, line.employee))
