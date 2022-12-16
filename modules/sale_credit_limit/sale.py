# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, Workflow
from trytond.pool import PoolMeta


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        for sale in sales:
            if sale.shipment_method == 'order':
                party = sale.invoice_party or sale.party
                party.check_credit_limit(sale.untaxed_amount, origin=str(sale))
        super(Sale, cls).confirm(sales)
