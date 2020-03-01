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
            ('project.work', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Work = pool.get('project.work')
        super().check_erase_company(party, company)

        works = Work.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', '!=', 'done'),
                ])
        if works:
            raise EraseError(
                gettext('project.msg_erase_party_opened_project',
                    party=party.rec_name,
                    company=company.rec_name))
