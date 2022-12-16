# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = ['Sale']


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def proceed(cls, sales):
        for sale in sales:
            if sale.state == 'confirmed' and sale.shipment_method == 'order':
                sale.party.check_credit_limit(sale.untaxed_amount,
                    origin=str(sale))
        return super(Sale, cls).proceed(sales)
