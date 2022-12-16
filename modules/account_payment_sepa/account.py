# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__all__ = ['Configuration']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    sepa_mandate_sequence = fields.Property(fields.Many2One('ir.sequence',
            'SEPA Mandate Sequence', domain=[
                ('code', '=', 'account.payment.sepa.mandate'),
                ('company', 'in', [Eval('context', {}).get('company', -1),
                        None]),
                ]))
