# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Case

from trytond.model import ModelSQL, ModelView, fields

__all__ = ['Routing', 'Operation', 'RoutingStep', 'Routing_BOM']


class Routing(ModelSQL, ModelView):
    'Routing'
    __name__ = 'production.routing'
    name = fields.Char('Name', required=True, translate=True)
    active = fields.Boolean('Active', select=True)
    steps = fields.One2Many('production.routing.step', 'routing', 'Steps')
    boms = fields.Many2Many(
        'production.routing-production.bom', 'routing', 'bom', 'BOMs')

    @classmethod
    def default_active(cls):
        return True


class Operation(ModelSQL, ModelView):
    'Operation'
    __name__ = 'production.routing.operation'
    name = fields.Char('Operation', required=True, translate=True)
    active = fields.Boolean('Active', select=True)

    @classmethod
    def default_active(cls):
        return True


class RoutingStep(ModelSQL, ModelView):
    'Route'
    __name__ = 'production.routing.step'
    _rec_name = 'operation'
    sequence = fields.Integer('Sequence')
    operation = fields.Many2One('production.routing.operation', 'Operation',
        required=True)
    routing = fields.Many2One('production.routing', 'Routing', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super(RoutingStep, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @classmethod
    def order_sequence(cls, tables):
        table, _ = tables[None]
        return [Case((table.sequence == Null, 0), else_=1), table.sequence]

    def get_rec_name(self, name):
        return self.operation.rec_name


class Routing_BOM(ModelSQL):
    'Routing - BOM'
    __name__ = 'production.routing-production.bom'
    routing = fields.Many2One('production.routing', 'Routing', required=True,
        select=True)
    bom = fields.Many2One('production.bom', 'BOM', required=True, select=True)
