# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin

__all__ = ['Party', 'PartyPaymentDirectDebit', 'PartyReplace']
payment_direct_debit = fields.Boolean(
    "Direct Debit", help="Check if supplier does direct debit.")


class Party:
    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    payment_direct_debit = fields.MultiValue(payment_direct_debit)
    payment_direct_debits = fields.One2Many(
        'party.party.payment_direct_debit', 'party', "Direct Debits")

    @classmethod
    def default_payment_direct_debit(cls, **pattern):
        return False


class PartyPaymentDirectDebit(ModelSQL, CompanyValueMixin):
    "Party Payment Direct Debit"
    __name__ = 'party.party.payment_direct_debit'
    party = fields.Many2One(
        'party.party', "Party", ondelete='CASCADE', select=True)
    payment_direct_debit = payment_direct_debit


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('account.payment', 'party'),
            ]
