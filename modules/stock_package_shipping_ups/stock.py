# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
import re
import ssl
import urllib.parse
from itertools import zip_longest

import requests

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.modules.stock_package_shipping.exceptions import (
    PackingValidationError)
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import StateAction, StateTransition, Wizard

from .exceptions import UPSError

TRACKING_URL = 'https://www.ups.com/track'
TIMEOUT = config.getfloat(
    'stock_package_shipping_ups', 'requests_timeout', default=300)


class PackageType(metaclass=PoolMeta):
    __name__ = 'stock.package.type'

    ups_code = fields.Selection([
            (None, ''),
            ('01', 'UPS Letter'),
            ('02', 'Customer Supplied Package'),
            ('03', 'Tube'),
            ('04', 'PAK'),
            ('21', 'UPS Express Box'),
            ('24', 'UPS 25KG Box'),
            ('25', 'UPS 10KG Box'),
            ('30', 'Pallet'),
            ('2a', 'Small Express Box'),
            ('2b', 'Medium Express Box'),
            ('2c', 'Large Express Box'),
            ('56', 'Flats'),
            ('57', 'Parcels'),
            ('58', 'BPM'),
            ('59', 'First Class'),
            ('60', 'Priority'),
            ('61', 'Machinables'),
            ('62', 'Irregulars'),
            ('63', 'Parcel Post'),
            ('64', 'BPM Parcel'),
            ('65', 'Media Mail'),
            ('66', 'BPM Flat'),
            ('67', 'Standard Flat'),
            ], 'UPS Code', sort=False, translate=False)

    @classmethod
    def default_ups_code(cls):
        return None


class Package(metaclass=PoolMeta):
    __name__ = 'stock.package'

    def get_shipping_tracking_url(self, name):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentInReturn = pool.get('stock.shipment.in.return')
        url = super().get_shipping_tracking_url(name)
        if (self.shipping_reference
                and self.shipment
                and self.shipment.id >= 0
                and self.shipment.carrier
                and self.shipment.carrier.shipping_service == 'ups'):
            party = address = None
            if isinstance(self.shipment, ShipmentOut):
                party = self.shipment.customer
                address = self.shipment.delivery_address
            elif isinstance(self.shipment, ShipmentInReturn):
                party = self.shipment.supplier
                address = self.shipment.delivery_address
            parts = urllib.parse.urlsplit(TRACKING_URL)
            query = urllib.parse.parse_qsl(parts.query)
            if party and party.lang and address and address.country:
                loc = '_'.join(
                    (party.lang.code.split('_')[0], address.country.code))
                query.append(('loc', loc))
            query.append(('tracknum', self.shipping_reference))
            parts = list(parts)
            parts[3] = urllib.parse.urlencode(query)
            url = urllib.parse.urlunsplit(parts)
        return url


class ShippingUPSMixin:
    __slots__ = ()

    def validate_packing_ups(self, usage=None):
        warehouse = self.shipping_warehouse
        if not warehouse.address:
            raise PackingValidationError(
                gettext('stock_package_shipping_ups'
                    '.msg_warehouse_address_required',
                    shipment=self.rec_name,
                    warehouse=warehouse.rec_name))
        if warehouse.address.country != self.delivery_address.country:
            for address in [self.shipping_to_address, warehouse.address]:
                if not address.contact_mechanism_get(
                        {'phone', 'mobile'}, usage=usage):
                    raise PackingValidationError(
                        gettext('stock_package_shipping_ups'
                            '.msg_phone_required',
                            shipment=self.rec_name,
                            address=address.rec_name))
            if not self.shipping_description:
                if (any(p.type.ups_code != '01' for p in self.root_packages)
                        and self.carrier.ups_service_type != '11'):
                    # TODO Should also test if a country is not in the EU
                    raise PackingValidationError(
                        gettext('stock_package_shipping_ups'
                            '.msg_shipping_description_required',
                            shipment=self.rec_name))


class ShipmentOut(ShippingUPSMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentInReturn(ShippingUPSMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class CreateShipping(metaclass=PoolMeta):
    __name__ = 'stock.shipment.create_shipping'

    ups = StateAction(
        'stock_package_shipping_ups.act_create_shipping_ups_wizard')

    def transition_start(self):
        next_state = super(CreateShipping, self).transition_start()
        if self.record.carrier.shipping_service == 'ups':
            next_state = 'ups'
        return next_state

    def do_ups(self, action):
        ctx = Transaction().context
        return action, {
            'model': ctx['active_model'],
            'id': ctx['active_id'],
            'ids': [ctx['active_id']],
            }


class CreateShippingUPS(Wizard):
    'Create UPS Shipping'
    __name__ = 'stock.shipment.create_shipping.ups'

    start = StateTransition()

    def transition_start(self):
        pool = Pool()
        Package = pool.get('stock.package')

        shipment = self.record
        if shipment.shipping_reference:
            raise AccessError(
                gettext('stock_package_shipping_ups'
                    '.msg_shipment_has_shipping_reference_number',
                    shipment=shipment.rec_name))

        credential = self.get_credential(shipment)
        carrier = shipment.carrier
        packages = shipment.root_packages
        shipment_request = self.get_request(shipment, packages, credential)
        token = credential.get_token()
        api_url = credential.get_shipment_url()
        headers = {
            'transactionSrc': "Tryton",
            'Authorization': f"Bearer {token}",
            }
        nb_tries, response = 0, None
        error_message = ''
        try:
            while nb_tries < 5 and response is None:
                try:
                    req = requests.post(
                        api_url, json=shipment_request, headers=headers,
                        timeout=TIMEOUT)
                except ssl.SSLError as e:
                    error_message = e.reason
                    nb_tries += 1
                    continue
                req.raise_for_status()
                response = req.json()
        except requests.HTTPError as e:
            error_message = e.args[0]

        if error_message:
            raise UPSError(
                gettext('stock_package_shipping_ups.msg_ups_webservice_error',
                    message=error_message))

        shipment_response = response['ShipmentResponse']
        response_status = shipment_response['Response']['ResponseStatus']
        if response_status['Code'] != '1':
            raise UPSError(
                gettext('stock_package_shipping_ups.msg_ups_webservice_error',
                    message=response_status['Description']))

        shipment_results = shipment_response['ShipmentResults']
        shipment.shipping_reference = (
            shipment_results['ShipmentIdentificationNumber'])
        ups_packages = shipment_results['PackageResults']
        if len(packages) == 1:
            # In case only one package is requested UPS returns a dictionnary
            # instead of a list of one package
            ups_packages = [ups_packages]

        for tryton_pkg, ups_pkg in zip_longest(packages, ups_packages):
            label = fields.Binary.cast(base64.b64decode(
                    ups_pkg['ShippingLabel']['GraphicImage']))
            tryton_pkg.shipping_reference = ups_pkg['TrackingNumber']
            tryton_pkg.shipping_label = label
            tryton_pkg.shipping_label_mimetype = (
                carrier.shipping_label_mimetype)
        Package.save(packages)
        shipment.save()

        return 'end'

    def get_credential_pattern(self, shipment):
        return {
            'company': shipment.company.id,
            }

    def get_credential(self, shipment):
        pool = Pool()
        UPSCredential = pool.get('carrier.credential.ups')

        credential_pattern = self.get_credential_pattern(shipment)
        for credential in UPSCredential.search([]):
            if credential.match(credential_pattern):
                return credential

    def get_request_container(self, shipment):
        return {
            'RequestOption': 'validate',
            'TransactionReference': {
                'CustomerContext': (shipment.number or '')[:512],
                },
            }

    def get_shipping_party(self, party, address, usage=None):
        shipping_party = {
            'Name': address.party_full_name[:35],
            'AttentionName': party.full_name[:35],
            'Address': {
                'AddressLine': [l[:35]
                    for l in (address.street or '').splitlines()[:3]],
                'City': address.city[:30],
                'PostalCode': (address.postal_code or '').replace(' ', '')[:9],
                'CountryCode': address.country.code if address.country else '',
                },
            }
        phone = address.contact_mechanism_get({'phone', 'mobile'}, usage=usage)
        if phone:
            shipping_party['Phone'] = {
                'Number': re.sub('[() .-]', '', phone.value)[:15]
                }
        email = address.contact_mechanism_get('email')
        if email and len(email.value) <= 50:
            shipping_party['EMailAddress'] = email.value

        return shipping_party

    def get_payment_information(self, shipment, credential):
        return {
            'ShipmentCharge': {
                # Type 01 is for Transportation Charges
                'Type': '01',
                'BillShipper': {
                    'AccountNumber': credential.account_number,
                    },
                },
            }

    def get_package(self, use_metric, package):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        cm = UoM(ModelData.get_id('product', 'uom_centimeter'))
        inch = UoM(ModelData.get_id('product', 'uom_inch'))

        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))
        lb = UoM(ModelData.get_id('product', 'uom_pound'))

        pkg = {
            'Packaging': {
                'Code': package.type.ups_code,
                },
            }
        if (package.length is not None
                and package.width is not None
                and package.height is not None):
            pkg['Dimensions'] = {
                'UnitOfMeasurement': {
                    'Code': 'CM' if use_metric else 'IN',
                    },
                'Length': '%i' % round(UoM.compute_qty(package.length_uom,
                        package.length, cm if use_metric else inch)),
                'Width': '%i' % round(UoM.compute_qty(package.width_uom,
                        package.width, cm if use_metric else inch)),
                'Height': '%i' % round(UoM.compute_qty(package.height_uom,
                        package.height, cm if use_metric else inch)),
                }
        if package.total_weight is not None:
            pkg['PackageWeight'] = {
                'UnitOfMeasurement': {
                    'Code': 'KGS' if use_metric else 'LBS',
                    },
                'Weight': str(UoM.compute_qty(kg, package.total_weight,
                        kg if use_metric else lb)),
                }
        return pkg

    def get_service_options(self, shipment):
        service_options = {}
        notifications = list(self.get_notifications(shipment))
        if notifications:
            service_options['Notification'] = notifications
        return service_options

    def get_notifications(self, shipment):
        if not shipment.carrier.ups_notifications:
            return
        for code in shipment.carrier.ups_notifications:
            shipping_to_address = shipment.shipping_to_address
            email = shipping_to_address.contact_mechanism_get('email')
            if email and len(email.value) <= 50:
                notification = {
                    'NotificationCode': code,
                    'EMail': {
                        'EMailAddress': email.value,
                        },
                    }
                if code in {'012', '013'}:
                    phone = shipping_to_address.contact_mechanism_get(
                        {'phone', 'mobile'})
                    if phone and len(phone.value) <= 15:
                        notification['VoiceMessage'] = {
                            'PhoneNumber': phone.value,
                            }
                    mobile = shipping_to_address.contact_mechanism_get(
                        'mobile')
                    if mobile and len(mobile.value) <= 15:
                        notification['TextMessage'] = {
                            'PhoneNumber': phone.value,
                            }
                yield notification

    def get_request(self, shipment, packages, credential):
        shipper = self.get_shipping_party(
            shipment.company.party, shipment.shipping_warehouse.address)
        shipper['ShipperNumber'] = credential.account_number
        # email is not required but must be associated with the UserId
        # which can not be ensured.
        shipper.pop('EMailAddress', None)

        packages = [self.get_package(credential.use_metric, p)
            for p in packages]
        options = self.get_service_options(shipment)
        if options:
            # options are set on package instead of shipment
            # despite what UPS documentation says
            for pkg in packages:
                pkg['ShipmentServiceOptions'] = options
        return {
            'ShipmentRequest': {
                'Request': self.get_request_container(shipment),
                'Shipment': {
                    'Description': (shipment.shipping_description or '')[:50],
                    'Shipper': shipper,
                    'ShipTo': self.get_shipping_party(
                        shipment.shipping_to, shipment.shipping_to_address),
                    'PaymentInformation': self.get_payment_information(
                        shipment, credential),
                    'Service': {
                        'Code': shipment.carrier.ups_service_type,
                        },
                    'Package': packages,
                    },
                'LabelSpecification': {
                    'LabelImageFormat': {
                        'Code': shipment.carrier.ups_label_image_format,
                        },
                    'LabelStockSize': {
                        'Width': '4',
                        'Height': shipment.carrier.ups_label_height,
                        },
                    }
                },
            }
