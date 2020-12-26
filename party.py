# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    stripe_customers = fields.One2Many(
        'account.payment.stripe.customer', 'party', "Stripe Customers")

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Customer = pool.get('account.payment.stripe.customer')

        parties = sum(args[0:None:2], [])
        customers = sum((p.stripe_customers for p in parties), ())
        customer2params = {c: c._customer_parameters() for c in customers}

        super().write(*args)

        to_update = []
        for customer, params in customer2params.items():
            if customer._customer_parameters() != params:
                to_update.append(customer)
        if to_update:
            Customer.__queue__.stripe_update(to_update)


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment.stripe.customer', 'party'),
            ]
