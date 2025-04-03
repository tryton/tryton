# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.i18n import gettext
from trytond.modules.stock_supply.exceptions import SupplyWarning
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import check_access
from trytond.wizard import StateAction


class OrderPoint(metaclass=PoolMeta):
    __name__ = 'stock.order_point'

    @classmethod
    def __setup__(cls):
        super().__setup__()

        cls.product.domain = [
            cls.product.domain,
            If(Eval('type') == 'production',
                ('producible', '=', True),
                ()),
            ]

        option = ('production', 'Production')
        if option not in cls.type.selection:
            cls.type.selection.append(option)

    @property
    def warehouse_location(self):
        location = super().warehouse_location
        if self.type == 'production':
            location = self.location
        return location


class LocationLeadTime(metaclass=PoolMeta):
    __name__ = 'stock.location.lead_time'

    @classmethod
    def _get_extra_lead_times(cls):
        pool = Pool()
        Configuration = pool.get('production.configuration')
        config = Configuration(1)
        supply_period = config.get_multivalue('supply_period')
        extra = super()._get_extra_lead_times()
        extra.append(supply_period or datetime.timedelta(0))
        return extra


class StockSupply(metaclass=PoolMeta):
    __name__ = 'stock.supply'

    production = StateAction('stock_supply_production.act_production_request')

    @classmethod
    def types(cls):
        return super().types() + ['production']

    def transition_create_(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Move = pool.get('stock.move')
        Warning = pool.get('res.user.warning')
        today = Date.today()
        with check_access():
            moves = Move.search([
                    ('from_location.type', '=', 'production'),
                    ('to_location.type', '=', 'storage'),
                    ('state', '=', 'draft'),
                    ('planned_date', '<', today),
                    ('production', 'not where', [
                            ('state', '=', 'request'),
                            ('origin', 'like', 'stock.order_point,%'),
                            ]),
                    ], order=[])
        if moves:
            key = '%s@%s' % (self.__name__, today)
            if Warning.check(key):
                raise SupplyWarning(
                    key,
                    gettext('stock_supply_production.msg_late_productions'))
        return super().transition_create_()

    @property
    def _production_parameters(self):
        return {
            'warehouses': self.start.warehouses,
            }

    def generate_production(self, clean):
        pool = Pool()
        Production = pool.get('production')
        return Production.generate_requests(
            clean=clean, **self._production_parameters)

    def transition_production(self):
        return self.next_action('production')
