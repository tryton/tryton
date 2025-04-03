# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, If


class Production(metaclass=PoolMeta):
    __name__ = 'production'
    routing = fields.Many2One('production.routing', 'Routing',
        domain=[
            If(Eval('state').in_(['request', 'draft']),
                ('boms', '=', Eval('bom', 0)),
                ()),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'invisible': ~Eval('bom'),
            })

    @fields.depends('bom', 'routing')
    def on_change_bom(self):
        super().on_change_bom()
        if self.bom:
            if self.routing:
                if self.bom not in self.routing.boms:
                    self.routing = None
        else:
            self.routing = None

    @fields.depends('routing')
    def compute_lead_time(self, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        pattern.setdefault(
            'routing', self.routing.id if self.routing else None)
        return super().compute_lead_time(pattern=pattern)

    @classmethod
    def compute_request(
            cls, product, warehouse, quantity, date, company,
            order_point=None, bom_pattern=None):
        production = super().compute_request(
            product, warehouse, quantity, date, company,
            order_point=order_point, bom_pattern=bom_pattern)
        if bom := product.get_bom(bom_pattern):
            production.routing = bom.routing
        return production
