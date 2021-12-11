# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, dualmethod, fields
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'
    warehouses = fields.Many2Many(
        'ir.cron-stock.warehouse', 'cron', 'warehouse',
        "Warehouses",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        help="Warehouses registered for this cron.")

    @dualmethod
    @ModelView.button
    def run_once(cls, crons):
        for cron in crons:
            if not cron.warehouses:
                super().run_once([cron])
            else:
                for warehouse in cron.warehouses:
                    with Transaction().set_context(warehouse=warehouse.id):
                        super(Cron, cls).run_once([cron])


class CronWarehouse(ModelSQL):
    "Cron - Warehouse"
    __name__ = 'ir.cron-stock.warehouse'
    cron = fields.Many2One(
        'ir.cron', "Cron", ondelete='CASCADE', required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", ondelete='CASCADE', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])
