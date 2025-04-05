# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields


class Allocation(ModelSQL, ModelView):
    __name__ = 'project.allocation'
    employee = fields.Many2One(
        'company.employee', "Employee", required=True, ondelete='CASCADE')
    work = fields.Many2One(
        'project.work', "Work", required=True, ondelete='CASCADE')
    percentage = fields.Float(
        "Percentage", digits=(None, 2), required=True,
        domain=[('percentage', '>', 0.0)])

    @staticmethod
    def default_percentage():
        return 100

    def get_rec_name(self, name):
        return self.employee.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('employee.rec_name',) + tuple(clause[1:])]

    @classmethod
    def on_modification(cls, mode, allocations, field_names=None):
        super().on_modification(mode, allocations, field_names=field_names)
        if mode in {'create', 'write'}:
            for allocation in allocations:
                allocation.work.reset_leveling()
                allocation.work.compute_dates()

    @classmethod
    def on_delete(cls, allocations):
        callback = super().on_delete(allocations)
        works = [a.work for a in allocations]

        def replan():
            for work in works:
                work.reset_leveling()
                work.compute_dates()
        callback.append(replan)
        return callback
