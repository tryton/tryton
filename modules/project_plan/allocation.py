#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields


class Allocation(ModelSQL, ModelView):
    'Allocation'
    _name = 'project.allocation'
    _description = __doc__

    _rec_name = 'employee'

    employee = fields.Many2One('company.employee', 'Employee', required=True,
            select=1)
    work = fields.Many2One('project.work', 'Work', required=True,
            select=1)
    percentage = fields.Float('Percentage', digits=(16, 2), required=True)

    def default_percentage(self, cursor, user_id, context=None):
        return 100

    def write(self, cursor, user, ids, values, context=None):
        work_obj = self.pool.get('project.work')
        res = super(Allocation, self).write(cursor, user, ids, values,
                context=context)

        if isinstance(ids, (int, long)):
            ids = [ids]
        work_ids = work_obj.search(cursor, user, [
                ('allocations', 'in', ids),
                ], context=context)

        for work_id in work_ids:
            work_obj.reset_leveling(cursor, user, work_id, context=context)
        for work_id in work_ids:
            work_obj.compute_dates(cursor, user, work_id, context=context)

        return res

    def create(self, cursor, user, values, context=None):
        work_obj = self.pool.get('project.work')
        allocation_id = super(Allocation, self).create(cursor, user, values,
                context=context)
        allocation = self.browse(cursor, user, allocation_id, context=context)
        work_obj.reset_leveling(cursor, user, allocation.work.id,
                context=context)
        work_obj.compute_dates(cursor, user, allocation.work.id,
                context=context)

    def delete(self, cursor, user, ids, context=None):
        work_obj = self.pool.get('project.work')
        allocations = self.browse(cursor, user, ids, context=context)
        work_ids = [a.work.id for a in allocations]
        res = super(Allocation, self).delete(cursor, user, ids,
                context=context)

        for work_id in work_ids:
            work_obj.reset_leveling(cursor, user, work_id, context=context)
        for work_id in work_ids:
            work_obj.compute_dates(cursor, user, work_id, context=context)

        return res


Allocation()
