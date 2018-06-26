# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Party']


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    stripe_customers = fields.One2Many(
        'account.payment.stripe.customer', 'party', "Stripe Customers")
