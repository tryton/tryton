#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields

class Party(ModelSQL, ModelView):
    _name = 'party.party'

    sale_price_list = fields.Property(type='many2one',
            relation='product.price_list', string='Sale Price List',
            domain=["('company', '=', company)"],
            states={
                'invisible': \
                        "not globals().get('company') or not bool(company)",
            })

Party()
