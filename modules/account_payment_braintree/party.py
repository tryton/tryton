# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from .common import BraintreeCustomerMethodMixin


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    braintree_customers = fields.One2Many(
        'account.payment.braintree.customer', 'party', "Braintree Customers")

    def _payment_identical_parties(self):
        parties = super()._payment_identical_parties()
        for customer in self.braintree_customers:
            for other_customer in customer.identical_customers:
                parties.add(other_customer.party)
        return parties

    @classmethod
    def on_write(cls, parties, values):
        pool = Pool()
        Customer = pool.get('account.payment.braintree.customer')
        transaction = Transaction()
        context = transaction.context

        callback = super().on_write(parties, values)

        customers = sum((p.braintree_customers for p in parties), ())
        if customers:
            customer2params = {c: c._customer_parameters() for c in customers}

            def update():
                to_update = []
                for customer, params in customer2params.items():
                    if customer._customer_parameters() != params:
                        to_update.append(customer)
                if to_update:
                    with transaction.set_context(
                            queue_batch=context.get('queue_batch', True)):
                        Customer.__queue__.braintree_update(to_update)
            callback.append(update)
        return callback


class PartyReceptionDirectDebit(
        BraintreeCustomerMethodMixin, metaclass=PoolMeta):
    __name__ = 'party.party.reception_direct_debit'

    def _get_payment(self, line, date, amount):
        payment = super()._get_payment(line, date, amount)
        payment.braintree_customer = self.braintree_customer
        payment.braintree_customer_method = self.braintree_customer_method
        return payment


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment.braintree.customer', 'party'),
            ]
