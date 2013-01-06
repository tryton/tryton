#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool

__all__ = ['Allocation']


class Allocation(ModelSQL, ModelView):
    'Allocation'
    __name__ = 'project.allocation'
    _rec_name = 'employee'
    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=True)
    work = fields.Many2One('project.work', 'Work', required=True,
            select=True)
    percentage = fields.Float('Percentage', digits=(16, 2), required=True)

    @classmethod
    def __setup__(cls):
        super(Allocation, cls).__setup__()
        cls._sql_constraints += [
            ('percentage_positive', 'CHECK(percentage > 0)',
                'Percentage must be greater than zero')
            ]

    @staticmethod
    def default_percentage():
        return 100

    @classmethod
    def write(cls, allocations, values):
        Work = Pool().get('project.work')
        super(Allocation, cls).write(allocations, values)

        works = Work.search([
                ('allocations', 'in', [a.id for a in allocations]),
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
