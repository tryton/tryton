# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import zip_longest

from trytond.i18n import gettext
from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import StateAction, StateTransition, Wizard


class Package(metaclass=PoolMeta):
    __name__ = 'stock.package'

    sendcloud_shipping_id = fields.Integer("ID", readonly=True)
    sendcloud_shipping_tracking_url = fields.Char(
        "Tracking URL", readonly=True)

    def get_shipping_tracking_url(self, name):
        url = super().get_shipping_tracking_url(name)
        if (self.shipping_reference
                and self.shipment
                and self.shipment.id >= 0
                and self.shipment.carrier
                and self.shipment.carrier.shipping_service == 'sendcloud'):
            url = self.sendcloud_shipping_tracking_url
        return url

    @classmethod
    def copy(cls, packages, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('sendcloud_shipping_id')
        default.setdefault('sendcloud_shipping_tracking_url')
        return super().copy(packages, default=default)


class ShippingSendcloudMixin:
    __slots__ = ()

    def get_sendcloud_credential(self):
        pool = Pool()
        SendcloudCredential = pool.get('carrier.credential.sendcloud')

        pattern = self._get_sendcloud_credential_pattern()
        for credential in SendcloudCredential.search([]):
            if credential.match(pattern):
                return credential

    def _get_sendcloud_credential_pattern(self):
        return {
            'company': self.company.id,
            }

    def validate_packing_sendcloud(self):
        pass


class ShipmentOut(ShippingSendcloudMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentInReturn(ShippingSendcloudMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class CreateShipping(metaclass=PoolMeta):
    __name__ = 'stock.shipment.create_shipping'

    sendcloud = StateAction(
        'stock_package_shipping_sendcloud.act_create_shipping_wizard')

    def transition_start(self):
        next_state = super().transition_start()
        if self.record.carrier.shipping_service == 'sendcloud':
            next_state = 'sendcloud'
        return next_state

    def do_sendcloud(self, action):
        ctx = Transaction().context
        return action, {
            'model': ctx['active_model'],
            'id': ctx['active_id'],
            'ids': [ctx['active_id']],
            }


class CreateShippingSendcloud(Wizard):
    "Create Sendcloud Shipping"
    __name__ = 'stock.shipment.create_shipping.sendcloud'

    start = StateTransition()

    def transition_start(self):
        pool = Pool()
        Package = pool.get('stock.package')

        shipment = self.record
        if shipment.reference:
            raise AccessError(
                gettext('stock_package_shipping_sendcloud'
                    '.msg_shipment_has_reference_number',
                    shipment=shipment.rec_name))

        credential = shipment.get_sendcloud_credential()
        carrier = shipment.carrier
        packages = shipment.root_packages

        parcels = []
        for package in packages:
            parcels.append(self.get_parcel(shipment, package, credential))
        parcels = credential.create_parcels(parcels)

        for package, parcel in zip_longest(packages, parcels):
            format_ = shipment.carrier.sendcloud_format.split()
            label_url = parcel['label']
            for key in format_:
                try:
                    index = int(key)
                except ValueError:
                    key += '_printer'
                    label_url = label_url[key]
                else:
                    label_url = label_url[index]
            package.sendcloud_shipping_id = parcel['id']
            package.shipping_label = credential.get_label(label_url)
            package.shipping_label_mimetype = carrier.shipping_label_mimetype
            package.shipping_reference = parcel['tracking_number']
            package.sendcloud_shipping_tracking_url = parcel['tracking_url']
            if not shipment.reference:
                shipment.reference = (
                    parcel['colli_tracking_number']
                    or parcel['tracking_number'])
        Package.save(packages)
        shipment.save()

        return 'end'

    def get_parcel(self, shipment, package, credential, usage=None):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        cm = UoM(ModelData.get_id('product', 'uom_centimeter'))
        party = shipment.shipping_to
        address = shipment.shipping_to_address
        phone = party.contact_mechanism_get(
            {'phone', 'mobile'}, usage=usage)
        email = party.contact_mechanism_get('email', usage=usage)
        street_lines = (address.street or '').splitlines()
        parcel = {
            'name': address.party_full_name,
            'company_name': (
                party.full_name if party.full_name != address.party_full_name
                else None),
            'address': street_lines[0] if street_lines else '',
            'address_2': (
                ' '.join(street_lines[1:]) if len(street_lines) > 1 else ''),
            'city': address.city,
            'postal_code': address.postal_code,
            'country': address.country.code if address.country else None,
            'country_state': (
                address.subdivision.code.split('-', 1)[1]
                if address.subdivision else None),
            'telephone': phone.value if phone else None,
            'email': email.value if email else None,
            'sender_address': credential.get_sender_address(shipment),
            'external_reference': '/'.join([shipment.number, package.code]),
            'quantity': 1,
            'order_number': shipment.number,
            'weight': package.total_weight,
            'length': UoM.compute_qty(package.length_uom, package.length, cm),
            'width': UoM.compute_qty(package.width_uom, package.width, cm),
            'height': UoM.compute_qty(package.height_uom, package.height, cm),
            'request_label': True,
            }
        shipping_method = credential.get_shipping_method(shipment)
        if shipping_method:
            parcel['shipment'] = {'id': shipping_method}
        else:
            parcel['apply_shipping_rules'] = True
        return parcel
