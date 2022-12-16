# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields

__all__ = ['Operation', 'RoutingStep']


class Operation:
    __metaclass__ = PoolMeta
    __name__ = 'production.routing.operation'
    work_center_category = fields.Many2One('production.work.center.category',
        'Work Center Category')


class RoutingStep:
    __metaclass__ = PoolMeta
    __name__ = 'production.routing.step'

    def get_work(self, production, work_center_picker):
        "Return work instance for the production using the work center picker"
        pool = Pool()
        Work = pool.get('production.work')

        work = Work()
        work.sequence = self.sequence
        work.operation = self.operation
        work.production = production
        work.company = production.company
        if self.operation.work_center_category:
            work.work_center = work_center_picker(
                production.work_center, self.operation.work_center_category)
        else:
            work.work_center = production.work_center
        return work
