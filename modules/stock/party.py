# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelSQL, ValueMixin, fields
from trytond.modules.party.exceptions import EraseError
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

supplier_location = fields.Many2One(
    'stock.location', "Supplier Location",
    ondelete='RESTRICT', domain=[('type', '=', 'supplier')],
    help="The default source location for stock received from the party.")
customer_location = fields.Many2One(
    'stock.location', "Customer Location",
    ondelete='RESTRICT', domain=[('type', '=', 'customer')],
    help="The default destination location for stock sent to the party.")


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    supplier_location = fields.MultiValue(supplier_location)
    customer_location = fields.MultiValue(customer_location)
    locations = fields.One2Many(
        'party.party.location', 'party', "Locations")
    delivered_to_warehouses = fields.Many2Many(
        'party.party-delivered_to-stock.location', 'party', 'location',
        "Delivered to Warehouses",
        domain=[
            ('type', '=', 'warehouse'),
            ],
        filter=[
            ('allow_pickup', '=', True),
            ])

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'supplier_location', 'customer_location'}:
            return pool.get('party.party.location')
        return super().multivalue_model(field)

    @classmethod
    def default_supplier_location(cls, **pattern):
        return cls.multivalue_model(
            'supplier_location').default_supplier_location()

    @classmethod
    def default_customer_location(cls, **pattern):
        return cls.multivalue_model(
            'customer_location').default_customer_location()

    def address_get(self, type=None):
        pool = Pool()
        Location = pool.get('stock.location')
        context = Transaction().context
        address = super().address_get(type=type)
        if (type == 'delivery'
                and context.get('warehouse')):
            warehouse = Location(context['warehouse'])
            if warehouse in self.delivered_to_warehouses:
                address = warehouse.address
        return address


class PartyLocation(ModelSQL, ValueMixin):
    __name__ = 'party.party.location'
    party = fields.Many2One('party.party', "Party", ondelete='CASCADE')
    supplier_location = supplier_location
    customer_location = customer_location

    @classmethod
    def default_supplier_location(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', 'location_supplier')
        except KeyError:
            return None

    @classmethod
    def default_customer_location(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id('stock', 'location_customer')
        except KeyError:
            return None


class PartyDeliveredToWarehouse(ModelSQL):
    __name__ = 'party.party-delivered_to-stock.location'

    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE')
    location = fields.Many2One(
        'stock.location', "Location", required=True, ondelete='CASCADE',
        domain=[
            ('type', '=', 'warehouse'),
            ])


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'
    delivery = fields.Boolean(
        'Delivery',
        help="Check to send deliveries to the address.")
    warehouses = fields.One2Many(
        'stock.location', 'address', "Warehouses", readonly=True)


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
