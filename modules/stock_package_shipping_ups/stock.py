# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import re
import base64
import requests
import ssl

from trytond.config import config
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateTransition, StateAction

__all__ = ['PackageType', 'ShipmentOut', 'CreateShipping', 'CreateShippingUPS']

SERVER_URLS = {
    'testing': 'https://wwwcie.ups.com/json/Ship',
    'production': 'https://onlinetools.ups.com/json/Ship',
    }


class PackageType:
    __metaclass__ = PoolMeta
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


class ShipmentOut:
    __metaclass__ = PoolMeta
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._error_messages.update({
                'warehouse_address_required': ('An address is required for'
                    ' warehouse "%(warehouse)s".'),
                'phone_required': ('A phone number is required for'
                    ' party "%(party)s".'),
                'shipping_description_required': ('A shipping description is'
                    ' required for shipment "%(shipment)s".'),
                })

    def validate_packing_ups(self):
        warehouse_address = self.warehouse.address
        if not warehouse_address:
            self.raise_user_error('warehouse_address_required', {
                    'warehouse': self.warehouse.rec_name,
                    })
        if warehouse_address.country != self.delivery_address.country:
            for party in {self.customer, self.company.party}:
                for mechanism in party.contact_mechanisms:
                    if mechanism.type in ('phone', 'mobile'):
                        break
                else:
                    self.raise_user_error('phone_required', {
                            'party': party.rec_name,
                            })
            if not self.shipping_description:
                if (any(p.type.ups_code != '01' for p in self.root_packages)
                        and self.carrier.ups_service_type != '11'):
                    # TODO Should also test if a country is not in the EU
                    self.raise_user_error('shipping_description_required', {
                            'shipment': self.rec_name,
                            })


class CreateShipping:
    __name__ = 'stock.shipment.create_shipping'
    __metaclass__ = PoolMeta

    ups = StateAction(
        'stock_package_shipping_ups.act_create_shipping_ups_wizard')

    def transition_start(self):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')

        shipment = ShipmentOut(Transaction().context['active_id'])
        next_state = super(CreateShipping, self).transition_start()
        if shipment.carrier.shipping_service == 'ups':
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

    @classmethod
    def __setup__(cls):
        super(CreateShippingUPS, cls).__setup__()
        cls._error_messages.update({
                'ups_webservice_error': ('UPS webservice call failed with the'
                    ' following error message:\n\n%(message)s'),
                'has_reference_number': ('Shipment "%(shipment)s" already has'
                    ' a reference number.'),
                })

    def transition_start(self):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        Package = pool.get('stock.package')

        shipment = ShipmentOut(Transaction().context['active_id'])
        if shipment.reference:
            self.raise_user_error('has_reference_number', {
                    'shipment': shipment.rec_name,
                    })

        credential = self.get_credential(shipment)
        packages = shipment.root_packages
        shipment_request = self.get_request(shipment, packages, credential)
        api_url = config.get('stock_package_shipping_ups', credential.server,
            default=SERVER_URLS[credential.server])
        nb_tries, response = 0, None
        error_message = ''
        try:
            while nb_tries < 5 and response is None:
                try:
                    req = requests.post(api_url, json=shipment_request)
                except ssl.SSLError as e:
                    error_message = e.message
                    nb_tries += 1
                    continue
                req.raise_for_status()
                response = req.json()
        except requests.HTTPError as e:
            error_message = e.message

        if error_message:
            self.raise_user_error('ups_webservice_error', {
                    'message': error_message,
                    })

        if 'Fault' in response:
            error = response['Fault']['detail']['Errors']
            message = '%s\n\n%s - %s' % (response['Fault']['faultstring'],
                error['ErrorDetail']['PrimaryErrorCode']['Code'],
                error['ErrorDetail']['PrimaryErrorCode']['Description'])
            self.raise_user_error('ups_webservice_error', {
                    'message': message,
                    })

        shipment_response = response['ShipmentResponse']
        response_status = shipment_response['Response']['ResponseStatus']
        if response_status['Code'] != '1':
            self.raise_user_error('ups_webservice_error', {
                    'message': response_status['Description'],
                    })

        shipment_results = shipment_response['ShipmentResults']
        shipment.reference = shipment_results['ShipmentIdentificationNumber']
        ups_packages = shipment_results['PackageResults']
        if len(packages) == 1:
            # In case only one package is requested UPS returns a dictionnary
            # instead of a list of one package
            ups_packages = [ups_packages]

        for tryton_pkg, ups_pkg in zip(packages, ups_packages):
            label = fields.Binary.cast(base64.b64decode(
                    ups_pkg['ShippingLabel']['GraphicImage']))
            tryton_pkg.shipping_reference = ups_pkg['TrackingNumber']
            tryton_pkg.shipping_label = label
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

    def get_security(self, credential):
        return {
            'UsernameToken': {
                'Username': credential.user_id,
                'Password': credential.password,
                },
            'ServiceAccessToken': {
                'AccessLicenseNumber': credential.license,
                },
            }

    def get_request_container(self, shipment):
        return {
            'RequestOption': 'validate',
            'TransactionReference': {
                'CustomerContext': (shipment.number or '')[:512],
                },
            }

    def get_shipping_party(self, party, address):
        shipping_party = {
            'Name': party.name[:35],
            'AttentionName': address.party.name[:35],
            'Address': {
                'AddressLine': [l[:35]
                    for l in (address.street or '').splitlines()[:3]],
                'City': address.city[:30],
                'PostalCode': (address.zip or '')[:9],
                'CountryCode': address.country.code if address.country else '',
                },
            }

        phone = ''
        for mechanism in party.contact_mechanisms:
            if mechanism.type in {'phone', 'mobile'}:
                phone = mechanism.value
                break
        if phone:
            shipping_party['Phone'] = {
                'Number': re.sub('[() .-]', '', phone)[:15]
                }

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

        return {
            'Packaging': {
                'Code': package.type.ups_code,
                },
            'Dimensions': {
                'UnitOfMeasurement': {
                    'Code': 'CM' if use_metric else 'IN',
                    },
                'Length': '%i' % round(UoM.compute_qty(package.type.length_uom,
                        package.type.length, cm if use_metric else inch)),
                'Width': '%i' % round(UoM.compute_qty(package.type.width_uom,
                        package.type.width, cm if use_metric else inch)),
                'Height': '%i' % round(UoM.compute_qty(package.type.height_uom,
                        package.type.height, cm if use_metric else inch)),
                },
            'PackageWeight': {
                'UnitOfMeasurement': {
                    'Code': 'KGS' if use_metric else 'LBS',
                    },
                'Weight': str(UoM.compute_qty(kg, package.total_weight,
                        kg if use_metric else lb)),
                },
            }

    def get_request(self, shipment, packages, credential):
        warehouse_address = shipment.warehouse.address
        shipper = self.get_shipping_party(shipment.company.party,
            warehouse_address)
        shipper['ShipperNumber'] = credential.account_number

        packages = [self.get_package(credential.use_metric, p)
            for p in packages]

        return {
            'UPSSecurity': self.get_security(credential),
            'ShipmentRequest': {
                'Request': self.get_request_container(shipment),
                'Shipment': {
                    'Description': (shipment.shipping_description or '')[:50],
                    'Shipper': shipper,
                    'ShipTo': self.get_shipping_party(shipment.customer,
                        shipment.delivery_address),
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
