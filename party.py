# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta, Pool

from trytond.modules.party.exceptions import EraseError


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'
    agents = fields.One2Many('commission.agent.selection', 'party', "Agents")


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('commission.agent', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Commission = pool.get('commission')
        super().check_erase_company(party, company)

        commissions = Commission.search([
                ('agent.party', '=', party.id),
                ('company', '=', company.id),
                ('invoice_line', '=', None),
                ])
        if commissions:
            raise EraseError(
                gettext('commission.msg_erase_party_pending_commission',
                    party=party.rec_name,
                    company=company.rec_name))
