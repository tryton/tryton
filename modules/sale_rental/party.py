# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('sale.rental', 'party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Rental = pool.get('sale.rental')
        super().check_erase_company(party, company)

        rentals = Rental.search([
                ('party', '=', party.id),
                ('company', '=', company.id),
                ('state', 'not in', ['done', 'cancelled']),
                ])
        if rentals:
            raise EraseError(
                gettext('sale_rental'
                    '.msg_erase_party_pending_rental',
                    party=party.rec_name,
                    company=company.rec_name))
