# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin

__all__ = ['Party', 'PartyPaymentDirectDebit', 'PartyReplace', 'PartyErase']
payment_direct_debit = fields.Boolean(
    "Direct Debit", help="Check if supplier does direct debit.")


class Party(metaclass=PoolMeta):
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


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('account.payment', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'pending_payment': (
                    'The party "%(party)s" can not be erased '
                    'because he has pending payments '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        Payment = pool.get('account.payment')
        super(PartyErase, self).check_erase_company(party, company)

        payments = Payment.search([
                ('party', '=', party.id),
                ('state', 'not in', ['succeeded', 'failed']),
                ])
        if payments:
            self.raise_user_error('pending_payment', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })
