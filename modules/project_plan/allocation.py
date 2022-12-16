#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool


class Allocation(ModelSQL, ModelView):
    'Allocation'
    _name = 'project.allocation'
    _description = __doc__
    _rec_name = 'employee'

    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=True)
    work = fields.Many2One('project.work', 'Work', required=True,
            select=True)
    percentage = fields.Float('Percentage', digits=(16, 2), required=True)

    def default_percentage(self):
        return 100

    def write(self, ids, values):
        work_obj = Pool().get('project.work')
        res = super(Allocation, self).write(ids, values)

        if isinstance(ids, (int, long)):
            ids = [ids]
        work_ids = work_obj.search([
                ('allocations', 'in', ids),
                ])

        for work_id in work_ids:
            work_obj.reset_leveling(work_id)
        for work_id in work_ids:
            work_obj.compute_dates(work_id)

        return res

    def create(self, values):
        work_obj = Pool().get('project.work')
        allocation_id = super(Allocation, self).create(values)
        allocation = self.browse(allocation_id)
        work_obj.reset_leveling(allocation.work.id)
        work_obj.compute_dates(allocation.work.id)

    def delete(self, ids):
        work_obj = Pool().get('project.work')
        allocations = self.browse(ids)
        work_ids = [a.work.id for a in allocations]
        res = super(Allocation, self).delete(ids)

        for work_id in work_ids:
            work_obj.reset_leveling(work_id)
        for work_id in work_ids:
            work_obj.compute_dates(work_id)

        return res

Allocation()
