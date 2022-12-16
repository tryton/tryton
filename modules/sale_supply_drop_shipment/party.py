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
            ('purchase.request', 'customer'),
            ('purchase.purchase', 'customer'),
            ('stock.shipment.drop', 'supplier'),
            ('stock.shipment.drop', 'customer'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        ShipmentDrop = pool.get('stock.shipment.drop')
        super().check_erase_company(party, company)

        shipments = ShipmentDrop.search([
                ['OR',
                    ('supplier', '=', party.id),
                    ('customer', '=', party.id),
                    ],
                ('company', '=', company.id),
                ('state', 'not in', ['done', 'cancel']),
                ])
        if shipments:
            raise EraseError(
                gettext('stock.msg_erase_party_shipment',
                    party=party.rec_name,
                    company=company.rec_name))
