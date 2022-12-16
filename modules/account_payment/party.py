# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, fields
from trytond.modules.company.model import CompanyValueMixin
from trytond.modules.party.exceptions import EraseError

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


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('account.payment', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Payment = pool.get('account.payment')
        super().check_erase_company(party, company)

        payments = Payment.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', 'not in', ['succeeded', 'failed']),
                ])
        if payments:
            raise EraseError(
                gettext('account_payment.msg_erase_party_pending_payment',
                    party=party.rec_name,
                    company=company.rec_name))
