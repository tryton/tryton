# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta


class PartyReceptionDirectDebit(metaclass=PoolMeta):
    __name__ = 'party.party.reception_direct_debit'

    def get_balance_pending_payment_domain(self):
        return [
            super().get_balance_pending_payment_domain(),
            ('clearing_move', '=', None),
            ]
