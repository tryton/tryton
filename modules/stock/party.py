# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

__all__ = ['PartyReplace', 'PartyErase']


class PartyReplace:
    __metaclass__ = PoolMeta
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super(PartyReplace, cls).fields_to_replace() + [
            ('stock.shipment.in', 'supplier'),
            ('stock.shipment.in.return', 'supplier'),
            ('stock.shipment.out', 'customer'),
            ('stock.shipment.out.return', 'customer'),
            ]


class PartyErase:
    __metaclass__ = PoolMeta
    __name__ = 'party.erase'

    @classmethod
    def __setup__(cls):
        super(PartyErase, cls).__setup__()
        cls._error_messages.update({
                'pending_shipment': (
                    'The party "%(party)s" can not be erased '
                    'because he has pending shipments '
                    'for the company "%(company)s".'),
                })

    def check_erase_company(self, party, company):
        pool = Pool()
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        super(PartyErase, self).check_erase_company(party, company)

        for Shipment, field in [
                (ShipmentIn, 'supplier'),
                (ShipmentInReturn, 'supplier'),
                (ShipmentOut, 'customer'),
                (ShipmentOutReturn, 'customer'),
                ]:
            shipments = Shipment.search([
                    (field, '=', party.id),
                    ('state', 'not in', ['done', 'cancel']),
                    ])
            if shipments:
                self.raise_user_error('pending_shipment', {
                        'party': party.rec_name,
                        'company': company.rec_name,
                        })
