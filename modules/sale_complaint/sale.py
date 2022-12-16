# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import unicode_literals

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Configuration', 'Sale']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration'

    complaint_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Complaint Sequence', domain=[
                ('code', '=', 'sale.complaint'),
                ['OR',
                    ('company', '=', Eval('context', {}).get('company', -1)),
                    ('company', '=', None),
                    ],
                ]))


class Sale:
    __metaclass__ = PoolMeta
    __name__ = 'sale.sale'

    @classmethod
    def _get_origin(cls):
        return super(Sale, cls)._get_origin() + ['sale.complaint']
