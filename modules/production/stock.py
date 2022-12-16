# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'
    production_location = fields.Many2One('stock.location', 'Production',
        states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ('type', '=', 'production'),
            ],
        depends=['type'])
    production_picking_location = fields.Many2One(
        'stock.location', "Production Picking",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id')]),
            ],
        depends=['type', 'id'],
        help="Where the production components are picked from.\n"
        "Leave empty to use the warehouse storage location.")
    production_output_location = fields.Many2One(
        'stock.location', "Production Output",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id')]),
            ],
        depends=['type', 'id'],
        help="Where the produced goods are stored.\n"
        "Leave empty to use the warehouse storage location.")


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    production_input = fields.Many2One('production', 'Production Input',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    production_output = fields.Many2One('production', 'Production Output',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    production_cost_price_updated = fields.Boolean(
        "Cost Price Updated", readonly=True,
        states={
            'invisible': ~Eval('production_input') & (Eval('state') == 'done'),
            },
        depends=['production_input', 'state'])

    def set_effective_date(self):
        if not self.effective_date and self.production_input:
            self.effective_date = self.production_input.effective_start_date
        if not self.effective_date and self.production_output:
            self.effective_date = self.production_output.effective_date
        super(Move, self).set_effective_date()

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cost_price_update = []
        actions = iter(args)
        for moves, values in zip(actions, actions):
            for move in moves:
                if (move.state == 'done'
                        and move.production_input
                        and 'cost_price' in values):
                    cost_price_update.append(move)
        if cost_price_update:
            cls.write(
                cost_price_update, {'production_cost_price_updated': True})


class ProductQuantitiesByWarehouseMove(metaclass=PoolMeta):
    __name__ = 'stock.product_quantities_warehouse.move'

    @classmethod
    def _get_document_models(cls):
        return super()._get_document_models() + ['production']

    def get_document(self, name):
        document = super().get_document(name)
        if self.move.production_input:
            document = str(self.move.production_input)
        if self.move.production_output:
            document = str(self.move.production_output)
        return document
