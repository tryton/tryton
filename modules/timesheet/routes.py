# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.protocols.wrappers import (
    Response, abort, allow_null_origin, user_application, with_pool,
    with_transaction)
from trytond.routing import Route, Router, Rule
from trytond.transaction import Transaction, without_check_access

timesheet_application = user_application('timesheet')


class Timesheet(Router):
    __name__ = 'timesheet'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__routes__.update({
                'employees': Route(
                    Rule('employees', methods={'GET'}),
                    Rule(
                        '/<database_name>/timesheet/'
                        'employees', methods={'GET'},
                        redirect_to='employees'),
                    decorators=[
                        allow_null_origin,
                        with_pool,
                        with_transaction(),
                        timesheet_application,
                        ]),
                'works': Route(
                    Rule('employee/<int:employee>/works', methods={'GET'}),
                    Rule(
                        '/<database_name>/timesheet/'
                        'employee/<int:employee>/works', methods={'GET'},
                        redirect_to='employee/<int:employee>/works'),
                    decorators=[
                        allow_null_origin,
                        with_pool,
                        with_transaction(),
                        timesheet_application,
                        ]),
                'lines': Route(
                    Rule(
                        'employee/<int:employee>/lines/<date>',
                        methods={'GET'}),
                    Rule(
                        '/<database_name>/timesheet/'
                        'employee/<int:employee>/lines/date', methods={'GET'},
                        redirect_to='employee/<int:employee>/lines/<date>'),
                    decorators=[
                        allow_null_origin,
                        with_pool,
                        with_transaction(),
                        timesheet_application,
                        ]),
                'line': Route(
                    Rule('line', methods={'POST'}),
                    Rule(
                        '/<database_name>/timesheet/'
                        'line', methods={'POST'},
                        redirect_to='line'),
                    Rule('line/<int:line>', methods={'PUT', 'DELETE'}),
                    Rule(
                        '/<database_name>/timesheet/'
                        'line/<int:line>', methods={'PUT', 'DELETE'},
                        redirect_to='line/<int:line>'),
                    decorators=[
                        allow_null_origin,
                        with_pool,
                        with_transaction(),
                        timesheet_application,
                        ]),
                })

    @classmethod
    def employees(cls, request, pool):
        User = pool.get('res.user')
        user = User(Transaction().user)
        return [{'id': e.id, 'name': e.rec_name} for e in user.employees]

    @classmethod
    def works(cls, request, pool, employee):
        Work = pool.get('timesheet.work')
        Employee = pool.get('company.employee')
        employee = Employee(employee)
        with Transaction().set_context(
                company=employee.company.id, employee=employee.id):
            works = Work.search([
                    ('company', '=', employee.company.id),
                    ])
        return sorted(({
                    'id': w.id,
                    'name': w.rec_name,
                    'start': (w.timesheet_start_date.strftime('%Y-%m-%d')
                        if w.timesheet_start_date else None),
                    'end': (w.timesheet_end_date.strftime('%Y-%m-%d')
                        if w.timesheet_end_date else None),
                    } for w in works),
            key=lambda w: w['name'].lower())

    @classmethod
    def lines(cls, request, pool, employee, date):
        User = pool.get('res.user')
        Employee = pool.get('company.employee')
        Line = pool.get('timesheet.line')

        employee = Employee(employee)
        date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        user = User(Transaction().user)
        if employee not in user.employees:
            abort(403)

        with Transaction().set_context(
                company=employee.company.id, employee=employee.id):
            lines = Line.search([
                    ('employee', '=', employee.id),
                    ('date', '=', date),
                    ],
                order=[('id', 'ASC')])
        return [l.to_json() for l in lines]

    @classmethod
    def line(cls, request, pool, line=None):
        Line = pool.get('timesheet.line')
        User = pool.get('res.user')
        Employee = pool.get('company.employee')
        if request.method in {'POST', 'PUT'}:
            data = request.parsed_data.copy()

            if not line and data.get('uuid'):
                lines = Line.search([
                        ('uuid', '=', data['uuid']),
                        ])
                if lines:
                    line, = lines

            if 'employee' in data:
                employee = Employee(data['employee'])
                data['company'] = employee.company.id
            else:
                employee = User(Transaction().user).employee
            if 'date' in data:
                data['date'] = datetime.datetime.strptime(
                    data['date'], '%Y-%m-%d').date()
            if 'duration' in data:
                data['duration'] = datetime.timedelta(
                    seconds=data['duration'])

            for extra in set(data) - set(Line._fields):
                del data[extra]

            with Transaction().set_context(
                    company=employee.company.id, employee=employee.id):
                if not line:
                    line, = Line.create([data])
                else:
                    lines = Line.search([('id', '=', int(line))])
                    if not lines:
                        return Response(None, 204)
                    line, = lines
                    Line.write(lines, data)
            return line.to_json()
        else:
            with without_check_access():
                lines = Line.search([('id', '=', line)])
            if lines:
                line, = lines
                with Transaction().set_context(
                        company=line.company.id, employee=line.employee.id):
                    lines = Line.search([('id', '=', line.id)])
                    Line.delete(lines)
            return Response(None, 204)
