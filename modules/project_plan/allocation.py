# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool

__all__ = ['Allocation']


class Allocation(ModelSQL, ModelView):
    'Allocation'
    __name__ = 'project.allocation'
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=True, ondelete='CASCADE')
    work = fields.Many2One('project.work', 'Work', required=True,
            select=True, ondelete='CASCADE')
    percentage = fields.Float('Percentage', digits=(16, 2), required=True,
        domain=[('percentage', '>', 0.0)])

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')

        super(Allocation, cls).__register__(module_name)

        # Migration from 3.2:
        table = TableHandler(cls, module_name)
        table.drop_constraint('percentage_positive')

    @staticmethod
    def default_percentage():
        return 100

    def get_rec_name(self, name):
        return self.employee.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('employee.rec_name',) + tuple(clause[1:])]

    @classmethod
    def write(cls, *args):
        Work = Pool().get('project.work')
        super(Allocation, cls).write(*args)

        works = Work.search([
                ('allocations', 'in',
                    [a.id for allocations in args[::2] for a in allocations]),
                ])

        for work in works:
            work.reset_leveling()
        for work in works:
            work.compute_dates()

    @classmethod
    def create(cls, vlist):
        allocations = super(Allocation, cls).create(vlist)
        for allocation in allocations:
            allocation.work.reset_leveling()
            allocation.work.compute_dates()
        return allocations

    @classmethod
    def delete(cls, allocations):
        works = [a.work for a in allocations]
        super(Allocation, cls).delete(allocations)

        for work in works:
            work.reset_leveling()
        for work in works:
            work.compute_dates()
