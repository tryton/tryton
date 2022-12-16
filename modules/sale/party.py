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
            ('sale.sale', 'party'),
            ('sale.sale', 'invoice_party'),
            ('sale.sale', 'shipment_party'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        Sale = pool.get('sale.sale')
        super().check_erase_company(party, company)

        sales = Sale.search([
                ['OR',
                    ('party', '=', party.id),
                    ('shipment_party', '=', party.id),
                    ],
                ('company', '=', company.id),
                ('state', 'not in', ['done', 'cancelled']),
                ])
        if sales:
            raise EraseError(
                gettext('sale.msg_erase_party_pending_sale',
                    party=party.rec_name,
                    company=company.rec_name))
