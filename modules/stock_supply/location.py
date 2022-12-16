# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.pyson import Eval


__all__ = ['Location', 'LocationLeadTime']


class Location(metaclass=PoolMeta):
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
    overflowing_location = fields.Many2One('stock.location',
        'Overflowing Location',
        states={
            'invisible': Eval('type') != 'storage',
            'readonly': ~Eval('active'),
            },
        domain=[
            ('type', 'in', ['storage', 'view']),
            ],
        depends=['type', 'active'],
        help='Leave empty for no default overflowing')


class LocationLeadTime(metaclass=PoolMeta):
    __name__ = 'stock.location.lead_time'

    @classmethod
    def get_max_lead_time(cls):
        """Return the biggest lead time
        increased by the maximum extra lead times"""
        lead_time = datetime.timedelta(0)
        lead_times = cls.search([])
        if lead_times:
            lead_time = sum(
                (r.lead_time for r in lead_times if r.lead_time),
                datetime.timedelta(0))
        extra_lead_times = cls._get_extra_lead_times()
        if extra_lead_times:
            lead_time += max(extra_lead_times)
        return lead_time

    @classmethod
    def _get_extra_lead_times(cls):
        'Return a list of extra lead time'
        pool = Pool()
        ProductSupplier = pool.get('purchase.product_supplier')
        extra = []

        product_suppliers = ProductSupplier.search(
            [('lead_time', '!=', None)],
            order=[('lead_time', 'DESC')], limit=1)
        if product_suppliers:
            product_supplier, = product_suppliers
            extra.append(product_supplier.lead_time)
        return extra
