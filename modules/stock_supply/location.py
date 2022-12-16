# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Location']


class Location:
    __metaclass__ = PoolMeta
    __name__ = 'stock.location'

    provisioning_location = fields.Many2One('stock.location',
        'Provisioning Location',
        states={
            'invisible': Eval('type') != 'storage',
            'readonly': ~Eval('active'),
            },
        domain=[
            ('type', 'in', ['storage', 'view']),
            ],
        depends=['type', 'active'],
        help='Leave empty for no default provisioning')
