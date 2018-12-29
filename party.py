# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool

from trytond.modules.party.exceptions import EraseError

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('purchase.product_supplier', 'party'),
            ('purchase.purchase', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Purchase = pool.get('purchase.purchase')
        super(PartyErase, self).check_erase_company(party, company)

        purchases = Purchase.search([
                ('party', '=', party.id),
                ('state', 'not in', ['done', 'cancel']),
                ])
        if purchases:
            raise EraseError(
                gettext('purchase.msg_erase_party_pending_purchase',
                    party=party.rec_name,
                    company=company.rec_name))
