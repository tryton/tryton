#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy

from trytond.model import Model
from trytond.pyson import Eval


class OrderPoint(Model):
    _name = 'stock.order_point'

    def __init__(self):
        super(OrderPoint, self).__init__()

        self.warehouse_location = copy.copy(self.warehouse_location)
        states = copy.copy(self.warehouse_location.states)
        states['invisible'] = (states['invisible']
            & (Eval('type') != 'production'))
        states['required'] = (states['required']
            | (Eval('type') == 'production'))
        self.warehouse_location.states = states

        option = ('production', 'Production')
        if option not in self.type.selection:
            self.type = copy.copy(self.type)
            self.type.selection = copy.copy(self.type.selection)
            self.type.selection.append(option)

        self._reset_columns()

    def _type2field(self, type=None):
        if type == 'production':
            return 'warehouse_location'
        result = super(OrderPoint, self)._type2field(type=type)
        if type == None:
            result['production'] = 'warehouse_location'
        return result

    def get_location(self, ids, name):
        locations = super(OrderPoint, self).get_location(ids, name)
        for op in self.browse(ids):
            if op.type == 'production':
                locations[op.id] = op.warehouse_location.id
        return locations

OrderPoint()
