# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.i18n import gettext
from trytond.model import Model, ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, shipments):
        super(ShipmentIn, cls).done(shipments)

        # Assigned sale move lines
        for shipment in shipments:
            shipment.assign_supplied()

    def assign_supplied(self, grouping=('product',), filter_=None):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        def filter_func(move):
            if filter_ is None:
                return True
            for fieldname, values in filter_:
                value = getattr(move, fieldname)
                if isinstance(value, Model):
                    value = value.id
                if value not in values:
                    return False

        def get_key(move):
            key = (move.to_location.id,)
            for field in grouping:
                value = getattr(move, field)
                if isinstance(value, Model):
                    value = value.id
                key += (value,)
            return key
        move_ids = [m.id for m in filter(filter_func, self.incoming_moves)]
        sale_lines = SaleLine.search([
                ('purchase_request.purchase_line.moves', 'in', move_ids),
                ('purchase_request.origin', 'like', 'sale.sale,%'),
                ])
        pbl = defaultdict(lambda: defaultdict(int))
        if self.warehouse_storage == self.warehouse_input:
            inventory_moves = self.incoming_moves
        else:
            inventory_moves = self.inventory_moves
        for move in filter(filter_func, inventory_moves):
            pbl[move.product][get_key(move)] += move.internal_quantity
        for sale_line in sale_lines:
            sale_line.assign_supplied(
                pbl[sale_line.product], grouping=grouping)


class OrderPoint(metaclass=PoolMeta):
    __name__ = 'stock.order_point'

    @fields.depends(methods=['_notify_product_supply_on_sale'])
    def on_change_notify(self):
        notifications = super().on_change_notify()
        notifications.extend(self._notify_product_supply_on_sale())
        return notifications

    @fields.depends('type', 'product')
    def _notify_product_supply_on_sale(self):
        if (self.type == 'purchase'
                and self.product and self.product.supply_on_sale):
            yield ('warning', gettext(
                    'sale_supply'
                    '.msg_order_point_product_supply_on_sale',
                    product=self.product.rec_name))
