# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('purchase.request', 'customer'),
            ('purchase.purchase', 'customer'),
            ('stock.shipment.drop', 'supplier'),
            ('stock.shipment.drop', 'customer'),
            ]


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        ShipmentDrop = pool.get('stock.shipment.drop')
        super(PartyErase, self).check_erase_company(party, company)

        shipments = ShipmentDrop.search([
                ['OR',
                    ('supplier', '=', party.id),
                    ('customer', '=', party.id),
                    ],
                ('state', 'not in', ['done', 'cancel']),
                ])
        if shipments:
            self.raise_user_error('pending_shipment', {
                    'party': party.rec_name,
                    'company': company.rec_name,
                    })
