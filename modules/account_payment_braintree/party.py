# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    braintree_customers = fields.One2Many(
        'account.payment.braintree.customer', 'party', "Braintree Customers")


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment.braintree.customer', 'party'),
            ]
