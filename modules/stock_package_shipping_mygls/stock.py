# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import BytesIO
from itertools import zip_longest

from PyPDF2 import PdfFileReader, PdfFileWriter

from trytond.i18n import gettext
from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.modules.stock_package_shipping.exceptions import (
    PackingValidationError)
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import StateAction, StateTransition, Wizard

from .api import get_client, get_request
from .exceptions import MyGLSError


class Package(metaclass=PoolMeta):
    __name__ = 'stock.package'

    mygls_shipping_id = fields.Integer("ID", readonly=True)

    @classmethod
    def copy(cls, packages, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('mygls_shipping_id')
        return super().copy(packages, default=default)


class ShippingMyGLSMixin:
    __slots__ = ()

    def get_mygls_credential(self):
        pool = Pool()
        Credential = pool.get('carrier.credential.mygls')

        pattern = self._get_mygls_credential_pattern()
        for credential in Credential.search([]):
            if credential.match(pattern):
                return credential

    def _get_mygls_credential_pattern(self):
        return {
            'company': self.company.id,
            'country': self.shipping_warehouse.address.country.code.lower(),
            }

    def validate_packing_mygls(self, usage=None):
        warehouse = self.shipping_warehouse
        if not warehouse.address:
            raise PackingValidationError(
                gettext('stock_package_shipping_mygls'
                    '.msg_warehouse_address_required',
                    shipment=self.rec_name,
                    warehouse=warehouse.rec_name))
        if not warehouse.address.country or not warehouse.address.country.code:
            raise PackingValidationError(
                gettext('stock_package_shipping_mygls'
                    '.msg_warehouse_address_country_code_required',
                    shipment=self.rec_name,
                    warehouse=warehouse.rec_name))
        shipping_to_address = self.shipping_to_address
        if (not shipping_to_address.country
                or not shipping_to_address.country.code):
            raise PackingValidationError(
                gettext('stock_package_shipping_mygls'
                    '.msg_shipping_to_address_country_code_required',
                    shipping=self.rec_name))
        if (self.carrier.mygls_services
                and 'CS1' in self.carrier.mygls_services):
            if not self.shipping_to.contact_mechanism_get(
                    {'phone', 'mobile'}, usage=usage):
                raise PackingValidationError(
                    gettext('stock_package_shipping_mygls'
                        '.msg_phone_mobile_required',
                        shipment=self.rec_name,
                        party=self.shipping_to.rec_name))
        if (self.carrier.mygls_services
                and 'FDS' in self.carrier.mygls_services):
            if not self.shipping_to.contact_mechanism_get(
                    'email', usage=usage):
                raise PackingValidationError(
                    gettext('stock_package_shipping_mygls'
                        '.msg_email_required',
                        shipment=self.rec_name,
                        party=self.shipping_to.rec_name))
        if (self.carrier.mygls_services
                and ('FSS' in self.carrier.mygls_services
                    or 'SM1' in self.carrier.mygls_services
                    or 'SM2' in self.carrier.mygls_services)):
            if not self.shipping_to.contact_mechanism_get(
                    'mobile', usage=usage):
                raise PackingValidationError(
                    gettext('stock_package_shipping_mygls'
                        '.msg_mobile_required',
                        shipment=self.rec_name,
                        party=self.shipping_to.rec_name))


class ShipmentOut(ShippingMyGLSMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentInReturn(ShippingMyGLSMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class ShipmentCreateShipping(metaclass=PoolMeta):
    __name__ = 'stock.shipment.create_shipping'

    mygls = StateAction(
        'stock_package_shipping_mygls.act_create_shipping_mygls_wizard')

    def transition_start(self):
        next_state = super().transition_start()
        if self.record.carrier.shipping_service == 'mygls':
            next_state = 'mygls'
        return next_state

    def do_mygls(self, action):
        ctx = Transaction().context
        return action, {
            'model': ctx['active_model'],
            'id': ctx['active_id'],
            'ids': [ctx['active_id']],
            }


class ShipmentCreateShippingMyGLS(Wizard):
    "Create MyGLS Shipping"
    __name__ = 'stock.shipment.create_shipping.mygls'

    start = StateTransition()

    def transition_start(self):
        pool = Pool()
        Package = pool.get('stock.package')

        shipment = self.record
        if shipment.reference:
            raise AccessError(
                gettext('stock_package_shipping_mygls'
                    '.msg_shipment_has_reference_number',
                    shipment=shipment.rec_name))

        credential = shipment.get_mygls_credential()
        client = get_client(credential, 'ParcelService')
        carrier = shipment.carrier
        packages = shipment.root_packages

        parcel = self.get_parcel(shipment, packages, credential)

        response = client.service.PrintLabels(**get_request(
                credential, 'printLabelsRequest',
                ParcelList=[{'Parcel': parcel}],
                TypeOfPrinter=carrier.mygls_type_of_printer,
                PrintPosition=carrier.mygls_print_position))

        if response.PrintLabelsErrorList:
            message = "\n".join(
                e.ErrorDescription
                for e in response.PrintLabelsErrorList.ErrorInfo)
            raise MyGLSError(
                gettext('stock_package_shipping_mygls.msg_mygls_api_error',
                    message=message))

        labels = []
        reader = PdfFileReader(BytesIO(response.Labels))
        for i in range(reader.getNumPages()):
            pdf = PdfFileWriter()
            label = BytesIO()
            pdf.addPage(reader.getPage(i))
            pdf.write(label)
            if carrier.mygls_type_of_printer in {'A4_2x2', 'A4_4x1'}:
                if carrier.mygls_type_of_printer == 'A4_2x2':
                    gap = carrier.mygls_print_position - 1
                else:
                    gap = 0
                max_label = ((i + 1) * 4) - gap
                n = 4
                if i == 0:
                    n -= gap
                if max_label > len(packages):
                    n -= max_label - len(packages)
                labels.extend([label] * n)
            else:
                labels.append(label)
        labels_info = response.PrintLabelsInfoList.PrintLabelsInfo

        for package, label, info in zip_longest(
                packages, labels, labels_info):
            package.mygls_shipping_id = info.ParcelId
            package.shipping_label = fields.Binary.cast(label.getvalue())
            package.shipping_label_mimetype = carrier.shipping_label_mimetype
            package.shipping_reference = info.ParcelNumber
            if not shipment.reference:
                shipment.reference = info.ParcelNumber
        Package.save(packages)
        shipment.save()

        return 'end'

    def get_parcel(self, shipment, packages, credential):
        services = []
        if shipment.carrier.mygls_services:
            for code in shipment.carrier.mygls_services:
                services.append({'Service': self.get_service(code, shipment)})
        return {
            'ClientNumber': credential.client_number,
            'ClientReference': shipment.number,
            'Count': len(packages),
            'Content': shipment.shipping_description,
            'PickupAddress': self.get_address(
                shipment.company.party,
                shipment.shipping_warehouse.address),
            'DeliveryAddress': self.get_address(
                shipment.shipping_to,
                shipment.shipping_to_address),
            'ServiceList': services,
            }

    def get_address(self, party, address, usage=None):
        phone = party.contact_mechanism_get({'phone', 'mobile'}, usage=usage)
        email = party.contact_mechanism_get('email', usage=usage)
        return {
            'Name': address.party_full_name,
            'Street': ' '.join((address.street or '').splitlines()),
            'City': address.city,
            'ZipCode': address.postal_code,
            'CountryIsoCode': address.country.code,
            'ContactName': party.full_name,
            'ContactPhone': phone.value if phone else None,
            'ContactEmail': email.value if email else None,
            }

    def get_service(self, code, shipment, usage=None):
        pool = Pool()
        Carrier = pool.get('carrier')
        service = {'Code': code}
        if code == 'AOS':
            service['AOSParameter'] = shipment.shipping_to.full_name,
        elif code == 'CS1':
            phone = shipment.shipping_to.contact_mechanism_get(
                    {'phone', 'mobile'}, usage=usage)
            service['CS1Parameter'] = phone.value
        elif code == 'FDS':
            email = shipment.shipping_to.contact_mechanism_get(
                'email', usage=usage)
            service['FDSParameter'] = email.value
        elif code == 'FSS':
            mobile = shipment.shipping_to.contact_mechanism_get(
                'mobile', usage=usage)
            service['FSSParameter'] = mobile.value
        elif code == 'SM1':
            if shipment.shipping_to.lang:
                lang_code = shipment.shipping_to.lang.code
            else:
                lang_code = None
            with Transaction().set_context(language=lang_code):
                carrier = Carrier(shipment.carrier.id)
            mobile = shipment.shipping_to.contact_mechanism_get(
                'mobile', usage=usage)
            service['SM1Parameter'] = '|'.join([
                    mobile.value, carrier.mygls_sms])
        elif code == 'SM2':
            mobile = shipment.shipping_to.contact_mechanism_get(
                'mobile', usage=usage)
            service['SM1Parameter'] = mobile.value
        return service
