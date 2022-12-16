# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.i18n import gettext
from trytond.pyson import Eval, If
from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateAction

from trytond.modules.stock_supply.exceptions import SupplyWarning


class OrderPoint(metaclass=PoolMeta):
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


class LocationLeadTime(metaclass=PoolMeta):
    __name__ = 'stock.location.lead_time'

    @classmethod
    def _get_extra_lead_times(cls):
        pool = Pool()
        Configuration = pool.get('production.configuration')
        config = Configuration(1)
        supply_period = config.get_multivalue('supply_period')
        extra = super(LocationLeadTime, cls)._get_extra_lead_times()
        extra.append(supply_period or datetime.timedelta(0))
        return extra


class StockSupply(metaclass=PoolMeta):
    __name__ = 'stock.supply'

    production = StateAction('stock_supply_production.act_production_request')

    @classmethod
    def types(cls):
        return super(StockSupply, cls).types() + ['production']

    def transition_create_(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('stock.move')
        Warning = pool.get('res.user.warning')
        today = Date.today()
        if Move.search([
                    ('from_location.type', '=', 'production'),
                    ('to_location.type', '=', 'storage'),
                    ('state', '=', 'draft'),
                    ('planned_date', '<', today),
                    ], order=[]):
            key = '%s@%s' % (self.__name__, today)
            if Warning.check(key):
                raise SupplyWarning(
                    key,
                    gettext('stock_supply_production.msg_late_productions'))
        return super(StockSupply, self).transition_create_()

    @property
    def _production_parameters(self):
        return {}

    def generate_production(self, clean):
        pool = Pool()
        Production = pool.get('production')
        return Production.generate_requests(
            clean=clean, **self._production_parameters)

    def transition_production(self):
        return self.next_action('production')
