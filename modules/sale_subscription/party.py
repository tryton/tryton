# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool

from trytond.modules.party.exceptions import EraseError


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('sale.subscription', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Subscription = pool.get('sale.subscription')
        super().check_erase_company(party, company)

        subscriptions = Subscription.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', 'not in', ['closed', 'cancelled']),
                ])
        if subscriptions:
            raise EraseError(
                gettext('sale_subscription'
                    '.msg_erase_party_pending_subscription',
                    party=party.rec_name,
                    company=company.rec_name))
