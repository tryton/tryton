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
            ('commission.agent', 'party'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Commission = pool.get('commission')
        super(PartyErase, self).check_erase_company(party, company)

        commissions = Commission.search([
                ('agent.party', '=', party.id),
                ('invoice_line', '=', None),
                ])
        if commissions:
            raise EraseError(
                gettext('commission.msg_erase_party_pending_commission',
                    party=party.rec_name,
                    company=company.rec_name))
