# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelView
from trytond.pool import PoolMeta

from .quality import ControlledMixin


class ControlledShipmentMixin(ControlledMixin):
    __slots__ = ()

    def quality_control_pattern(self, operation):
        pattern = super().quality_control_pattern(operation)
        pattern['company'] = self.company.id
        pattern['products'] = {m.product.id for m in self.moves}
        return pattern


class ShipmentIn(ControlledShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'receive', 'quality.wizard_stock_shipment_in_inspect_receive')
    def receive(cls, shipments):
        return super().receive(shipments)

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'do', 'quality.wizard_stock_shipment_in_inspect_do')
    def do(cls, shipments):
        return super().do(shipments)


class ShipmentOut(ControlledShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'pick', 'quality.wizard_stock_shipment_out_inspect_pick')
    def pick(cls, shipments):
        return super().pick(shipments)

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'pack', 'quality.wizard_stock_shipment_out_inspect_pack')
    def pack(cls, shipments):
        return super().pack(shipments)


class ShipmentOutReturn(ControlledShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'receive', 'quality.wizard_stock_shipment_out_return_inspect_receive')
    def receive(cls, shipments):
        return super().receive(shipments)

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'do', 'quality.wizard_stock_shipment_out_return_inspect_do')
    def do(cls, shipments):
        return super().do(shipments)


class ShipmentInternal(ControlledShipmentMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'ship', 'quality.wizard_stock_shipment_internal_inspect_ship')
    def ship(cls, shipments):
        return super().ship(shipments)

    @classmethod
    @ModelView.button
    @ControlledMixin.control(
        'do', 'quality.wizard_stock_shipment_internal_inspect_do')
    def do(cls, shipments):
        return super().do(shipments)
