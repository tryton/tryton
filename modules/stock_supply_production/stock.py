#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta

__all__ = ['OrderPoint']
__metaclass__ = PoolMeta


class OrderPoint:
    __name__ = 'stock.order_point'

    @classmethod
    def __setup__(cls):
        super(OrderPoint, cls).__setup__()

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
