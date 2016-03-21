# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Production']


class Production:
    __metaclass__ = PoolMeta
    __name__ = 'production'
    routing = fields.Many2One('production.routing', 'Routing',
        domain=[
            ('boms', '=', Eval('bom', 0)),
            ],
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'invisible': ~Eval('bom'),
            },
        depends=['bom', 'state'])

    @fields.depends('bom', 'routing')
    def on_change_bom(self):
        super(Production, self).on_change_bom()
        if self.bom:
            if self.routing:
                if self.bom not in self.routing.boms:
                    self.routing = None
        else:
            self.routing = None

    @classmethod
    def compute_request(cls, product, warehouse, quantity, date, company):
        production = super(Production, cls).compute_request(
            product, warehouse, quantity, date, company)
        production.routing = product.boms[0].routing if product.boms else None
        return production
