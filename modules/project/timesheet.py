# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


class Line(metaclass=PoolMeta):
    __name__ = 'timesheet.line'

    @classmethod
    def default_work(cls):
        pool = Pool()
        Work = pool.get('timesheet.work')
        try:
            default = super().default_work()
        except AttributeError:
            default = None
        project_works = Transaction().context.get('project.work')
        if project_works is not None:
            works = Work.search([
                    ('origin.id', 'in', project_works, 'project.work'),
                    ])
            if len(works) == 1:
                default = works[0].id
        return default


class Work(metaclass=PoolMeta):
    __name__ = 'timesheet.work'

    @classmethod
    def _get_origin(cls):
        return super()._get_origin() + ['project.work']

    def _validate_company(self):
        pool = Pool()
        ProjectWork = pool.get('project.work')
        result = super()._validate_company()
        if isinstance(self.origin, ProjectWork):
            result &= self.company == self.origin.company
        return result
