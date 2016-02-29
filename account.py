# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['Configuration', 'Move']


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'
    asset_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Asset Reference Sequence', domain=[
                ('company', 'in', [Eval('context', {}).get('company', -1),
                        None]),
                ('code', '=', 'account.asset'),
                ], required=True))


class Move:
    __metaclass__ = PoolMeta
    __name__ = 'account.move'

    @classmethod
    def _get_origin(cls):
        origins = super(Move, cls)._get_origin()
        origins.append('account.asset')
        origins.append('account.asset.line')
        return origins
