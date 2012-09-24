#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['Party']
__metaclass__ = PoolMeta


class Party:
    __name__ = 'party.party'
    sale_price_list = fields.Property(fields.Many2One('product.price_list',
            'Sale Price List',
            domain=[
                ('company', '=', Eval('context', {}).get('company')),
                ],
            states={
                'invisible': ~Eval('context', {}).get('company'),
                }))
