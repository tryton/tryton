# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('sale.subscription', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'pending_subscription': (
                    'The party "%(party)s" can not be erased '
                    'because he has pending subscriptions '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        Subscription = pool.get('sale.subscription')
        super(PartyErase, self).check_erase_company(party, company)

        subscriptions = Subscription.search([
                ('party', '=', party.id),
                ('state', 'not in', ['closed', 'canceled']),
                ])
        if subscriptions:
            self.raise_user_error('pending_subscription', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })
