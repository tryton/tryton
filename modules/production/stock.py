# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta


__all__ = ['Location', 'Move']


class Location:
    __metaclass__ = PoolMeta
    __name__ = 'stock.location'
    production_location = fields.Many2One('stock.location', 'Production',
        states={
            'invisible': Eval('type') != 'warehouse',
            'readonly': ~Eval('active'),
            'required': Eval('type') == 'warehouse',
            },
        domain=[
            ('type', '=', 'production'),
            ],
        depends=['type', 'active'])


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'stock.move'
    production_input = fields.Many2One('production', 'Production Input',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    production_output = fields.Many2One('production', 'Production Output',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])

    def set_effective_date(self):
        if not self.effective_date and self.production_input:
            self.effective_date = self.production_input.effective_date
        if not self.effective_date and self.production_output:
            self.effective_date = self.production_output.effective_date
        super(Move, self).set_effective_date()
