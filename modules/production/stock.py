# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Cast, Null
from sql.conditionals import Case
from sql.operators import Concat

from trytond.model import Check, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If


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
    production_input = fields.Many2One(
        'production', "Production Input", readonly=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('production_output', None),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('production_input'),
            })
    production_output = fields.Many2One(
        'production', "Production Output", readonly=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('production_input', None),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': ~Eval('production_output'),
            })
    production = fields.Function(fields.Many2One(
            'production', "Production",
            states={
                'invisible': ~Eval('production'),
                }),
        'on_change_with_production', searcher='search_production')
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
        cls._allow_modify_closed_period.add('production_cost_price_updated')

    @fields.depends(
        'production_output', '_parent_production_output.company',
        'to_location')
    def on_change_production_output(self):
        if self.production_output:
            if self.production_output.company:
                self.currency = self.production_output.company.currency
            if self.to_location and self.to_location.type == 'lost_found':
                self.currency = None

    @fields.depends(
        'production_output', '_parent_production_output.id', 'to_location')
    def on_change_to_location(self):
        try:
            super().on_change_to_location()
        except AttributeError:
            pass
        if (self.production_output
                and self.to_location
                and self.to_location.type == 'lost_found'):
            self.currency = None

    @fields.depends(
        'production_input', '_parent_production_input.id',
        'production_output', '_parent_production_output.id')
    def on_change_with_production(self, name=None):
        if self.production_input:
            return self.production_input
        elif self.production_output:
            return self.production_output

    @classmethod
    def search_production(cls, name, clause):
        _, operator, operand, *extra = clause
        if operator.startswith('!') or operator.startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        nested = clause[0][len(name):]
        return [bool_op,
            ('production_input' + nested, operator, operand, *extra),
            ('production_output' + nested, operator, operand, *extra),
            ]

    def set_effective_date(self):
        if not self.effective_date and self.production_input:
            self.effective_date = self.production_input.effective_start_date
        if not self.effective_date and self.production_output:
            self.effective_date = self.production_output.effective_date
        super().set_effective_date()

    @classmethod
    def on_modification(cls, mode, moves, field_names=None):
        super().on_modification(mode, moves, field_names=field_names)
        if mode == 'write' and 'cost_price' in field_names:
            cls.write(
                [m for m in moves if m.state == 'done' and m.production_input],
                {'production_cost_price_updated': True})


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
    def _columns(cls, tables):
        move = tables['move']
        return super()._columns(tables) + [
            move.production_input.as_('production_input'),
            move.production_output.as_('production_output'),
            ]

    @classmethod
    def get_documents(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        return super().get_documents() + [
            ('production', Model.get_name('production'))]

    @classmethod
    def get_document(cls, tables):
        document = super().get_document(tables)
        sql_type = cls.document.sql_type().base
        move = tables['move']
        return Case(
            ((move.production_input != Null),
                Concat('production,',
                    Cast(move.production_input, sql_type))),
            ((move.production_output != Null),
                Concat('production,',
                    Cast(move.production_output, sql_type))),
            else_=document)

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
