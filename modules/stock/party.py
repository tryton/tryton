# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta, Pool

from trytond.modules.party.exceptions import EraseError


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'
    delivery = fields.Boolean(
        'Delivery',
        help="Check to send deliveries to the address.")


class ContactMechanism(metaclass=PoolMeta):
    __name__ = 'party.contact_mechanism'
    delivery = fields.Boolean(
        'Delivery',
        help="Check to use for delivery.")

    @classmethod
    def usages(cls, _fields=None):
        if _fields is None:
            _fields = []
        _fields.append('delivery')
        return super().usages(_fields=_fields)


class Replace(metaclass=PoolMeta):
    __name__ = 'party.replace'

    @classmethod
    def fields_to_replace(cls):
        return super().fields_to_replace() + [
            ('stock.shipment.in', 'supplier'),
            ('stock.shipment.in.return', 'supplier'),
            ('stock.shipment.out', 'customer'),
            ('stock.shipment.out.return', 'customer'),
            ]


class Erase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase_company(self, party, company):
        pool = Pool()
        ShipmentIn = pool.get('stock.shipment.in')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentOutReturn = pool.get('stock.shipment.out.return')
        super().check_erase_company(party, company)

        for Shipment, field in [
                (ShipmentIn, 'supplier'),
                (ShipmentInReturn, 'supplier'),
                (ShipmentOut, 'customer'),
                (ShipmentOutReturn, 'customer'),
                ]:
            shipments = Shipment.search([
                    (field, '=', party.id),
                    ('company', '=', company.id),
                    ('state', 'not in', ['done', 'cancelled']),
                    ])
            if shipments:
                raise EraseError(
                    gettext('stock.msg_erase_party_shipment',
                        party=party.rec_name,
                        company=company.rec_name))
