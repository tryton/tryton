# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta


__all__ = ['ShipmentIn']


class ShipmentIn:
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.in'

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        SaleLine = Pool().get('sale.line')

        super(ShipmentIn, cls).done(shipments)

        # Assigned sale move lines
        for shipment in shipments:
            move_ids = [x.id for x in shipment.incoming_moves]
            sale_lines = SaleLine.search([
                    ('purchase_request.purchase_line.moves',
                        'in', move_ids),
                    ('purchase_request.origin', 'like', 'sale.sale,%'),
                    ])
            pbl = defaultdict(lambda: defaultdict(lambda: 0))
            for move in shipment.inventory_moves:
                pbl[move.product][move.to_location] += move.internal_quantity
            for sale_line in sale_lines:
                sale_line.assign_supplied(pbl[sale_line.product])
