# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields

__all__ = ['Party', 'PartyReplace']


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    payment_direct_debit_int = fields.Property(
        fields.Integer("Direct Debit Internal"))
    payment_direct_debit = fields.Function(
        fields.Boolean(
            "Direct Debit", help="Check if supplier does direct debit."),
        'get_payment_direct_debit', setter='set_payment_direct_debit')

    @classmethod
    def default_payment_direct_debit(cls):
        return False

    def get_payment_direct_debit(self, name):
        return bool(self.payment_direct_debit_int)

    @classmethod
    def set_payment_direct_debit(cls, parties, name, value):
        cls.write(parties, {
                'payment_direct_debit_int': (
                    int(value) if value is not None else None),
                })


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('account.payment', 'party'),
            ]
