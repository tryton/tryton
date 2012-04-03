#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Eval, Bool, Not, Get


class Party(ModelSQL, ModelView):
    _name = 'party.party'

    sale_price_list = fields.Property(fields.Many2One('product.price_list',
            'Sale Price List',
            domain=[
                ('company', '=', Get(Eval('context', {}), 'company')),
                ],
            states={
                'invisible': Not(Bool(Get(Eval('context', {}), 'company'))),
                }))

Party()
