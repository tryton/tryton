# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, dualmethod, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'
    warehouses = fields.Many2Many(
        'ir.cron-stock.warehouse', 'cron', 'warehouse',
        "Warehouses",
        states={
            'readonly': Eval('running', False),
            'invisible': ~Eval('warehouse_needed', False),
            },
        domain=[
            ('type', '=', 'warehouse'),
            If(~Eval('warehouse_needed'),
                ('id', '=', None),
                ()),
            ],
        help="Warehouses registered for this cron.")
    warehouse_needed = fields.Function(fields.Boolean(
            "Warehouse Needed"),
        'on_change_with_warehouse_needed')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.methods_warehouse_needed = {
            'product.product|recompute_cost_price_from_moves',
            }

    @fields.depends('method')
    def on_change_with_warehouse_needed(self, name=None):
        return self.method in self.__class__.methods_warehouse_needed

    @fields.depends('warehouses', methods=['on_change_with_company_needed'])
    def on_change_method(self):
        pool = Pool()
        Warehouse = pool.get('stock.location')
        if self.on_change_with_warehouse_needed():
            self.warehouses = Warehouse.search([
                    ('type', '=', 'warehouse'),
                    ])
        else:
            self.warehouses = []

    @dualmethod
    @ModelView.button
    def run_once(cls, crons):
        for cron in crons:
            if not cron.warehouses:
                super().run_once([cron])
            else:
                for warehouse in cron.warehouses:
                    with Transaction().set_context(warehouse=warehouse.id):
                        super().run_once([cron])


class CronWarehouse(ModelSQL):
    __name__ = 'ir.cron-stock.warehouse'
    cron = fields.Many2One(
        'ir.cron', "Cron", ondelete='CASCADE', required=True)
    warehouse = fields.Many2One(
        'stock.location', "Warehouse", ondelete='CASCADE', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])
