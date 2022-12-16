# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from .common import StripeCustomerMethodMixin


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    stripe_customers = fields.One2Many(
        'account.payment.stripe.customer', 'party', "Stripe Customers")

    def _payment_identical_parties(self):
        parties = super()._payment_identical_parties()
        for customer in self.stripe_customers:
            for other_customer in customer.identical_customers:
                parties.add(other_customer.party)
        return parties

    @classmethod
    def write(cls, *args):
        pool = Pool()
        Customer = pool.get('account.payment.stripe.customer')
        transaction = Transaction()
        context = transaction.context

        parties = sum(args[0:None:2], [])
        customers = sum((p.stripe_customers for p in parties), ())
        customer2params = {c: c._customer_parameters() for c in customers}

        super().write(*args)

        to_update = []
        for customer, params in customer2params.items():
            if customer._customer_parameters() != params:
                to_update.append(customer)
        if to_update:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Customer.__queue__.stripe_update(to_update)


class PartyReceptionDirectDebit(
        StripeCustomerMethodMixin, metaclass=PoolMeta):
    __name__ = 'party.party.reception_direct_debit'

    def _get_payment(self, line, date, amount):
        payment = super()._get_payment(line, date, amount)
        self.stripe_customer = self.stripe_customer
        self.stripe_customer_source = self.stripe_customer_source
        self.stripe_customer_payment_method = (
            self.stripe_customer_payment_method)
        return payment


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment.stripe.customer', 'party'),
            ]
