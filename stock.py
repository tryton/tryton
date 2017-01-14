# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pyson import Eval, If
from trytond.pool import PoolMeta, Pool

__all__ = ['OrderPoint', 'LocationLeadTime']


class OrderPoint:
    __metaclass__ = PoolMeta
    __name__ = 'stock.order_point'

    @classmethod
    def __setup__(cls):
        super(OrderPoint, cls).__setup__()

        cls.product.domain = [
            cls.product.domain,
            If(Eval('type') == 'production',
                ('producible', '=', True),
                ()),
            ]
        if 'type' not in cls.product.depends:
            cls.product.depends.append('type')

        cls.warehouse_location.states['invisible'] &= (
            Eval('type') != 'production')
        cls.warehouse_location.states['required'] |= (
            Eval('type') == 'production')

        option = ('production', 'Production')
        if option not in cls.type.selection:
            cls.type.selection.append(option)

    @classmethod
    def _type2field(cls, type=None):
        if type == 'production':
            return 'warehouse_location'
        result = super(OrderPoint, cls)._type2field(type=type)
        if type is None:
            result['production'] = 'warehouse_location'
        return result

    def get_location(self, name):
        location = super(OrderPoint, self).get_location(name)
        if self.type == 'production':
            return self.warehouse_location.id
        return location


class LocationLeadTime:
    __metaclass__ = PoolMeta
    __name__ = 'stock.location.lead_time'

    @classmethod
    def _get_extra_lead_times(cls):
        pool = Pool()
        Configuration = pool.get('production.configuration')
        extra = super(LocationLeadTime, cls)._get_extra_lead_times()
        extra.append(datetime.timedelta(Configuration(1).supply_period or 0))
        return extra
