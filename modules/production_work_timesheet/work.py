# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Work']


class Work(metaclass=PoolMeta):
    __name__ = 'production.work'

    timesheet_works = fields.One2Many(
        'timesheet.work', 'origin', 'Timesheet Works', readonly=True, size=1)
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
                ('work', 'in', Eval('timesheet_works', [])),
                ],
            depends=['timesheet_works', 'company']),
        'get_timesheet_lines', setter='set_timesheet_lines')

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
    def create(cls, vlist):
        works = super(Work, cls).create(vlist)
        cls._set_timesheet_work(works)
        return works

    @classmethod
    def write(cls, *args):
        super(Work, cls).write(*args)
        works = sum(args[0:None:2], [])
        cls._set_timesheet_work(works)

    @classmethod
    def delete(cls, works):
        pool = Pool()
        TimesheetWork = pool.get('timesheet.work')

        timesheet_works = [w for pw in works for w in pw.timesheet_works]

        super(Work, cls).delete(works)

        if timesheet_works:
            TimesheetWork.delete(timesheet_works)

    @classmethod
    def _set_timesheet_work(cls, productions):
        pool = Pool()
        Timesheet = pool.get('timesheet.work')
        Date = pool.get('ir.date')
        today = Date.today()

        to_create = []
        to_delete = []
        to_write = defaultdict(list)
        for production in productions:
            if production.timesheet_available:
                ended = production.state in {'done', 'cancelled'}
                if not production.timesheet_works:
                    to_create.append({
                            'origin': str(production),
                            'company': production.company.id,
                            'timesheet_end_date': today if ended else None,
                            })
                elif ended:
                    for timesheet in production.timesheet_works:
                        date = max([today]
                            + [l.date for l in timesheet.timesheet_lines])
                        to_write[date].append(timesheet)
            if (not production.timesheet_available
                    and production.timesheet_works):
                if all(not w.timesheet_lines
                        for w in production.timesheet_works):
                    to_delete.extend(production.timesheet_works)
        if to_create:
            Timesheet.create(to_create)
        if to_delete:
            Timesheet.delete(to_delete)
        for date, timesheets in list(to_write.items()):
            Timesheet.write(timesheets, {
                    'timesheet_end_date': date,
                    })
