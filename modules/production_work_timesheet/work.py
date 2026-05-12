# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Literal
from sql.aggregate import Sum
from sql.conditionals import Coalesce
from sql.functions import Extract

from trytond import backend
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.tools import sqlite_apply_types
from trytond.transaction import Transaction


class WorkCenter(metaclass=PoolMeta):
    __name__ = 'production.work.center'

    include_timesheet_cost = fields.Boolean(
        "Include Timesheet Cost",
        help="Check to add the timesheet cost to the work cost.")

    @classmethod
    def default_include_timesheet_cost(cls):
        return False


class Work(metaclass=PoolMeta):
    __name__ = 'production.work'

    timesheet_works = fields.One2Many(
        'timesheet.work', 'origin', 'Timesheet Works', readonly=True, size=1)
    timesheet_work = fields.Function(
        fields.Many2One('timesheet.work', "Timesheet Work"),
        'get_timesheet_work')
    timesheet_available = fields.Function(
        fields.Boolean('Available on timesheets'),
        'on_change_with_timesheet_available')
    timesheet_lines = fields.Function(
        fields.One2Many('timesheet.line', None, 'Timesheet Lines',
            states={
                'invisible': ~Eval('timesheet_works'),
                },
            domain=[
                ('company', '=', Eval('company', -1)),
                ('work', '=', Eval('timesheet_work', -1)),
                ]),
        'get_timesheet_lines', setter='set_timesheet_lines')

    def get_timesheet_work(self, name):
        if self.timesheet_works:
            timesheet_work, = self.timesheet_works
            return timesheet_work.id

    @fields.depends('operation')
    def on_change_with_timesheet_available(self, name=None):
        if self.operation:
            return self.operation.timesheet_available

    def get_timesheet_lines(self, name):
        if self.timesheet_works:
            return [l.id for w in self.timesheet_works
                for l in w.timesheet_lines]
        else:
            return []

    @classmethod
    def set_timesheet_lines(cls, works, name, value):
        pool = Pool()
        TimesheetWork = pool.get('timesheet.work')
        if value:
            timesheet_works = [tw for w in works for tw in w.timesheet_works]
            TimesheetWork.write(timesheet_works, {
                    'timesheet_lines': value,
                    })

    @classmethod
    def on_modification(cls, mode, works, field_names=None):
        super().on_modification(mode, works, field_names=field_names)
        if mode in {'create', 'write'}:
            cls._set_timesheet_work(works)

    @classmethod
    def on_delete(cls, works):
        pool = Pool()
        TimesheetWork = pool.get('timesheet.work')
        callback = super().on_delete(works)
        timesheet_works = [w for pw in works for w in pw.timesheet_works]
        callback.append(lambda: TimesheetWork.delete(timesheet_works))
        return callback

    @classmethod
    def _set_timesheet_work(cls, works):
        pool = Pool()
        Timesheet = pool.get('timesheet.work')
        Date = pool.get('ir.date')

        to_create = []
        to_delete = []
        to_write = defaultdict(list)
        for work in works:
            with Transaction().set_context(company=work.company.id):
                today = Date.today()
            if work.timesheet_available:
                ended = work.state in {'done', 'cancelled'}
                if not work.timesheet_works:
                    to_create.append({
                            'origin': str(work),
                            'company': work.company.id,
                            'timesheet_end_date': today if ended else None,
                            })
                elif ended:
                    for timesheet in work.timesheet_works:
                        date = max([today]
                            + [l.date for l in timesheet.timesheet_lines])
                        to_write[date].append(timesheet)
            if (not work.timesheet_available
                    and work.timesheet_works):
                if all(not w.timesheet_lines
                        for w in work.timesheet_works):
                    to_delete.extend(work.timesheet_works)
        if to_create:
            Timesheet.create(to_create)
        if to_delete:
            Timesheet.delete(to_delete)
        for date, timesheets in list(to_write.items()):
            Timesheet.write(timesheets, {
                    'timesheet_end_date': date,
                    })


class Work_TimesheetCost(metaclass=PoolMeta):
    __name__ = 'production.work'

    @classmethod
    def _get_cost(cls, works):
        pool = Pool()
        Line = pool.get('timesheet.line')
        TimesheetWork = pool.get('timesheet.work')
        Work = pool.get('production.work')
        WorkCenter = pool.get('production.work.center')
        line = Line.__table__()
        t_work = TimesheetWork.__table__()
        work = Work.__table__()
        center = WorkCenter.__table__()

        cursor = Transaction().connection.cursor()

        costs = super()._get_cost(works)

        cost = line.cost_price * Extract('EPOCH', line.duration) / (60 * 60)
        work_origin = TimesheetWork.origin.sql_id(t_work.origin, TimesheetWork)
        query = line.join(
            t_work, condition=(t_work.id == line.work)).join(
            work, condition=(work.id == work_origin)).join(
            center, condition=(
                (center.id == work.work_center)
                & (center.include_timesheet_cost == Literal(True)))
            ).select(work.id, Sum(Coalesce(cost, 0)).as_('cost'),
            where=(
                fields.SQL_OPERATORS['in'](work_origin, map(int, works))
                & (t_work.origin.like(cls.__name__ + ',%'))),
            group_by=work.id)
        if backend.name == 'sqlite':
            sqlite_apply_types(query, [None, 'NUMERIC'])
        cursor.execute(*query)
        for work_id, cost in cursor:
            costs[work_id] += cost
        return costs
