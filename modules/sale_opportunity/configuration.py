#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['Configuration']
__metaclass__ = PoolMeta


class Configuration:
    'Sale Configuration'
    __name__ = 'sale.configuration'
    sale_opportunity_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Opportunity Reference Sequence', domain=[
                ('company', 'in', [Eval('context', {}).get('company', -1),
                        None]),
                ('code', '=', 'sale.opportunity'),
                ], required=True))
