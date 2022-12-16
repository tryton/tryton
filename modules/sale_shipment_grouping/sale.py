# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.transaction import Transaction


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @property
    def shipment_grouping_method(self):
        return self.party.sale_shipment_grouping_method

    @property
    def _shipment_grouping_fields(self):
        return ('customer', 'delivery_address', 'company', 'warehouse')

    def _get_grouped_shipment_planned_date(self, shipment):
        return [('planned_date', '=', shipment.planned_date)]

    def _get_grouped_shipment_order(self):
        "Returns the order used to find shipments that should be grouped"
        return None

    def _get_grouped_shipment_domain(self, shipment):
        "Returns a domain that will find shipments that should be grouped"
        Shipment = shipment.__class__
        shipment_domain = [
            ('moves.origin', 'like', 'sale.line,%'),
            ('state', 'in', ['draft', 'waiting']),
            ]
        shipment_domain += self._get_grouped_shipment_planned_date(shipment)
        defaults = Shipment.default_get(self._shipment_grouping_fields,
            with_rec_name=False)
        for field in self._shipment_grouping_fields:
            shipment_domain.append((field, '=',
                    getattr(shipment, field, defaults.get(field))))
        return shipment_domain

    def _get_shipment_sale(self, shipment_type, values):
        transaction = Transaction()
        context = transaction.context
        shipment = super(Sale, self)._get_shipment_sale(shipment_type, values)
        if (not context.get('skip_grouping', False)
                and self.shipment_grouping_method):
            with transaction.set_context(skip_grouping=True):
                shipment = self._get_shipment_sale(shipment_type, values)
            Shipment = shipment.__class__
            domain = self._get_grouped_shipment_domain(shipment)
            order = self._get_grouped_shipment_order()
            grouped_shipments = Shipment.search(domain, order=order, limit=1)
            if grouped_shipments:
                shipment, = grouped_shipments
        return shipment
