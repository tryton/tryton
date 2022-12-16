# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.model import Check, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'
    production_location = fields.Many2One('stock.location', 'Production',
        states={
            'invisible': Eval('type') != 'warehouse',
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ('type', '=', 'production'),
            ])
    production_picking_location = fields.Many2One(
        'stock.location', "Production Picking",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id', -1)]),
            ],
        help="Where the production components are picked from.\n"
        "Leave empty to use the warehouse storage location.")
    production_output_location = fields.Many2One(
        'stock.location', "Production Output",
        states={
            'invisible': Eval('type') != 'warehouse',
            },
        domain=[
            ('type', '=', 'storage'),
            ('parent', 'child_of', [Eval('id', -1)]),
            ],
        help="Where the produced goods are stored.\n"
        "Leave empty to use the warehouse storage location.")


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    production_input = fields.Many2One('production', 'Production Input',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        states={
            'invisible': ~Eval('production_input'),
            })
    production_output = fields.Many2One('production', 'Production Output',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        states={
            'invisible': ~Eval('production_output'),
            })
    production = fields.Function(fields.Many2One(
            'production', "Production",
            states={
                'invisible': ~Eval('production'),
                }),
        'on_change_with_production')
    production_cost_price_updated = fields.Boolean(
        "Cost Price Updated", readonly=True,
        states={
            'invisible': ~Eval('production_input') & (Eval('state') == 'done'),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('production_single', Check(t, (
                        (t.production_input == Null)
                        | (t.production_output == Null))),
                'production.msg_stock_move_production_single'),
            ]

    @fields.depends(
        'production_input', '_parent_production_input.id',
        'production_output', '_parent_production_output.id')
    def on_change_with_production(self, name=None):
        if self.production_input:
            return self.production_input.id
        elif self.production_output:
            return self.production_output.id

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


class LotTrace(metaclass=PoolMeta):
    __name__ = 'stock.lot.trace'

    production_input = fields.Many2One('production', "Production Input")
    production_output = fields.Many2One('production', "Production Output")

    @classmethod
    def _columns(cls, move):
        return super()._columns(move) + [
            move.production_input.as_('production_input'),
            move.production_output.as_('production_output'),
            ]

    @classmethod
    def get_documents(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return super().get_documents() + [
            ('production', Model.get_name('production'))]

    def get_document(self, name):
        document = super().get_document(name)
        if self.production_input:
            document = str(self.production_input)
        elif self.production_output:
            document = str(self.production_output)
        return document

    def _get_upward_traces(self):
        traces = super()._get_upward_traces()
        if self.production_input:
            traces.update(self.production_input.outputs)
        return traces

    def _get_downward_traces(self):
        traces = super()._get_downward_traces()
        if self.production_output:
            traces.update(self.production_output.inputs)
        return traces
