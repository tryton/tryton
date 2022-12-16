# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Party']


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    sale_invoice_grouping_method = fields.Property(fields.Selection([
                (None, 'None'),
                ('standard', 'Standard'),
                ],
            'Sale Invoice Grouping Method'))
