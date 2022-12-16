#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Model, fields
from trytond.pyson import Eval


class Location(Model):
    _name = 'stock.location'

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

Location()


class Move(Model):
    _name = 'stock.move'

    production_input = fields.Many2One('production', 'Production Input',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    production_output = fields.Many2One('production', 'Production Output',
        readonly=True, select=True, ondelete='CASCADE',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])

Move()
