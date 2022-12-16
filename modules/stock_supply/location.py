# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Location', 'LocationLeadTime']


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


class LocationLeadTime:
    __metaclass__ = PoolMeta
    __name__ = 'stock.location.lead_time'

    @classmethod
    def get_max_lead_time(cls):
        'Return the biggest lead time'
        lead_times = cls.search([])
        if lead_times:
            return max(r.lead_time for r in lead_times)
        else:
            return datetime.timedelta(0)
