# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, Workflow
from trytond.pool import PoolMeta


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    def must_check_credit_limit(self):
        return self.shipment_method == 'order'

    @property
    def credit_limit_amount(self):
        "Amount to check against credit limit"
        return self.untaxed_amount

    @classmethod
    @ModelView.button
    @Workflow.transition('confirmed')
    def confirm(cls, sales):
        for sale in sales:
            if sale.must_check_credit_limit():
                party = sale.invoice_party or sale.party
                party.check_credit_limit(
                    sale.credit_limit_amount, origin=str(sale))
        super(Sale, cls).confirm(sales)
