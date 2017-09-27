# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields, sequence_ordered

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


class RoutingStep(sequence_ordered(), ModelSQL, ModelView):
    'Route'
    __name__ = 'production.routing.step'
    operation = fields.Many2One('production.routing.operation', 'Operation',
        required=True)
    routing = fields.Many2One('production.routing', 'Routing', required=True,
        ondelete='CASCADE')

    def get_rec_name(self, name):
        return self.operation.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('operation.rec_name',) + tuple(clause[1:])]


class Routing_BOM(ModelSQL):
    'Routing - BOM'
    __name__ = 'production.routing-production.bom'
    routing = fields.Many2One('production.routing', 'Routing', required=True,
        select=True)
    bom = fields.Many2One('production.bom', 'BOM', required=True, select=True)
