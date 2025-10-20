# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    def shipment_grouping_method(self):
        return self.party.sale_shipment_grouping_method

    @property
    def _shipment_grouping_origins(self):
        return ['sale.line']

    @property
    def _shipment_grouping_state(self):
        return {'draft', 'waiting'}

    def _get_shipment_grouping_fields(self, shipment):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        fields = {'customer', 'company', 'warehouse'}
        if isinstance(shipment, ShipmentOut):
            fields.add('delivery_address')
        return fields

    def _get_grouped_shipment_planned_date(self, shipment):
        return [('planned_date', '=', shipment.planned_date)]

    def _get_grouped_shipment_order(self, Shipment):
        "Returns the order used to find shipments that should be grouped"
        return None

    def _get_grouped_shipment_domain(self, shipment):
        "Returns a domain that will find shipments that should be grouped"
        Shipment = shipment.__class__
        shipment_domain = [
            ['OR'] + [
                ('moves.origin', 'like', f'{o},%')
                for o in self._shipment_grouping_origins],
            ('state', 'in', list(self._shipment_grouping_state)),
            ]
        shipment_domain += self._get_grouped_shipment_planned_date(shipment)
        fields = self._get_shipment_grouping_fields(shipment)
        defaults = Shipment.default_get(fields, with_rec_name=False)
        for field in fields:
            shipment_domain.append((field, '=',
                    getattr(shipment, field, defaults.get(field))))
        return shipment_domain

    def _get_shipment_sale(self, Shipment, values):
        transaction = Transaction()
        context = transaction.context
        shipment = super()._get_shipment_sale(Shipment, values)
        if (not context.get('skip_grouping', False)
                and self.shipment_grouping_method):
            with transaction.set_context(skip_grouping=True):
                shipment = self._get_shipment_sale(Shipment, values)
            domain = self._get_grouped_shipment_domain(shipment)
            order = self._get_grouped_shipment_order(Shipment)
            grouped_shipments = Shipment.search(domain, order=order, limit=1)
            if grouped_shipments:
                origin_planned_date = shipment.origin_planned_date
                shipment, = grouped_shipments
                if origin_planned_date:
                    if not shipment.origin_planned_date:
                        shipment.origin_planned_date = origin_planned_date
                    elif shipment.origin_planned_date > origin_planned_date:
                        shipment.origin_planned_date = origin_planned_date
        return shipment

    @classmethod
    def _process_shipment(cls, sales):
        for method, sales in groupby(
                sales, lambda s: s.shipment_grouping_method):
            if method:
                for sale in sales:
                    super()._process_shipment([sale])
            else:
                super()._process_shipment(list(sales))
