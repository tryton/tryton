# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta

from .exceptions import ShippingBlocked


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        pool = Pool()
        Sale = pool.get('sale.sale')

        sales = {
            move.sale for shipment in shipments for move in shipment.moves
            if move.sale}
        for sale in Sale.browse(sales):
            if sale.shipping_blocked:
                raise ShippingBlocked(
                    gettext('sale_advance_payment.msg_shipping_blocked',
                        sale=sale.rec_name))
        super().pack(shipments)
