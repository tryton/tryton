# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, Workflow
from trytond.pool import Pool, PoolMeta

__all__ = ['ShipmentOut']


class ShipmentOut(metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
                'advance_payment_not_paid': ('The customer has not paid the'
                    ' required advance payment amount for the sale'
                    ' "%(sale)s".'),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('packed')
    def pack(cls, shipments):
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        sales = {move.origin.sale
            for shipment in shipments for move in shipment.moves
            if isinstance(move.origin, SaleLine)}
        for sale in Sale.browse([s.id for s in sales]):
            if sale.shipping_blocked:
                cls.raise_user_error('advance_payment_not_paid', {
                        'sale': sale.rec_name,
                        })
        super(ShipmentOut, cls).pack(shipments)
