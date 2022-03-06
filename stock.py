# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import locale
from io import BytesIO
from itertools import zip_longest

from lxml import etree
from PyPDF2 import PdfFileReader, PdfFileWriter
from zeep.exceptions import Fault

from trytond.i18n import gettext
from trytond.model import fields
from trytond.model.exceptions import AccessError
from trytond.modules.stock_package_shipping.exceptions import (
    PackingValidationError)
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import StateAction, StateTransition, Wizard

from .configuration import SHIPMENT_SERVICE, get_client
from .exceptions import DPDError

TRACKING_URL = 'https://tracking.dpd.de/status/%(code)s/parcel/%(reference)s'


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
                and self.shipment.carrier.shipping_service == 'dpd'):
            party = address = None
            if isinstance(self.shipment, ShipmentOut):
                party = self.shipment.customer
                address = self.shipment.delivery_address
            elif isinstance(self.shipment, ShipmentInReturn):
                party = self.shipment.supplier
                address = self.shipment.delivery_address
            if party and party.lang:
                lang_code = party.lang.code
            else:
                lang_code = Transaction().language
            if address and address.country:
                code = '_'.join(
                    (lang_code.split('_')[0], address.country.code))
            else:
                code = lang_code
            url = TRACKING_URL % {
                'code': code,
                'reference': self.shipping_reference,
                }
        return url


class ShippingDPDMixin:
    __slots__ = ()

    def validate_packing_dpd(self):
        warehouse = self.shipping_warehouse
        if not warehouse.address:
            raise PackingValidationError(
                gettext('stock_package_shipping_dpd'
                    '.msg_warehouse_address_required',
                    shipment=self.rec_name,
                    warehouse=warehouse.rec_name))


class ShipmentOut(ShippingDPDMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'


class ShipmentInReturn(ShippingDPDMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'


class CreateShipping(metaclass=PoolMeta):
    __name__ = 'stock.shipment.create_shipping'

    dpd = StateAction(
        'stock_package_shipping_dpd.act_create_shipping_dpd_wizard')

    def transition_start(self):
        next_state = super(CreateShipping, self).transition_start()
        if self.record.carrier.shipping_service == 'dpd':
            next_state = 'dpd'
        return next_state

    def do_dpd(self, action):
        ctx = Transaction().context
        return action, {
            'model': ctx['active_model'],
            'id': ctx['active_id'],
            'ids': [ctx['active_id']],
            }


class CreateDPDShipping(Wizard):
    'Create DPD Shipping'
    __name__ = 'stock.shipment.create_shipping.dpd'

    start = StateTransition()

    def transition_start(self):
        pool = Pool()
        Package = pool.get('stock.package')

        shipment = self.record
        if shipment.reference:
            raise AccessError(
                gettext('stock_package_shipping_dpd'
                    '.msg_shipment_has_reference_number',
                    shipment=shipment.rec_name))

        credential = self.get_credential(shipment)
        if not credential.depot or not credential.token:
            credential.update_token()

        carrier = shipment.carrier
        shipping_client = get_client(credential.server, SHIPMENT_SERVICE)
        print_options = self.get_print_options(shipment)
        packages = shipment.root_packages
        shipment_data = self.get_shipment_data(credential, shipment, packages)

        count = 0
        while count < 2:
            lang = (credential.company.party.lang.code
                if credential.company.party.lang else 'en')
            lang = locale.normalize(lang)[:5]
            authentication = {
                'delisId': credential.user_id,
                'authToken': credential.token,
                'messageLanguage': lang,
                }
            try:
                shipment_response = shipping_client.service.storeOrders(
                    print_options, shipment_data, _soapheaders={
                        'authentication': authentication,
                        })
                break
            except Fault as e:
                if e.detail:
                    tag = etree.QName(e.detail[0].tag)
                    if tag.localname == 'authenticationFault':
                        count += 1
                        credential.update_token()
                        continue
                raise DPDError(gettext(
                        'stock_package_shipping_dpd.'
                        'msg_dpd_webservice_error',
                        message=e.message)) from e
        else:
            raise DPDError(
                gettext('stock_package_shipping_dpd.msg_dpd_login_error',
                    credential=credential.rec_name))

        response, = shipment_response.shipmentResponses
        if response.faults:
            message = '\n'.join(f.message for f in response.faults)
            raise DPDError(
                gettext('stock_package_shipping_dpd.msg_dpd_webservice_error',
                    message=message))

        labels = []
        labels_pdf = BytesIO(shipment_response.parcellabelsPDF)
        reader = PdfFileReader(labels_pdf)
        for page_num in range(reader.getNumPages()):
            new_pdf = PdfFileWriter()
            new_label = BytesIO()
            new_pdf.addPage(reader.getPage(page_num))
            new_pdf.write(new_label)
            labels.append(new_label)

        shipment.reference = response.mpsId
        parcels = response.parcelInformation
        for package, label, parcel in zip_longest(packages, labels, parcels):
            package.shipping_label = fields.Binary.cast(label.getvalue())
            package.shipping_label_mimetype = (
                carrier.shipping_label_mimetype)
            package.shipping_reference = parcel.parcelLabelNumber
        Package.save(packages)
        shipment.save()

        return 'end'

    def get_credential_pattern(self, shipment):
        return {
            'company': shipment.company.id,
            }

    def get_credential(self, shipment):
        pool = Pool()
        DPDCredential = pool.get('carrier.credential.dpd')

        credential_pattern = self.get_credential_pattern(shipment)
        for credential in DPDCredential.search([]):
            if credential.match(credential_pattern):
                return credential

    def get_print_options(self, shipment):
        return {
            'printerLanguage': shipment.carrier.dpd_printer_language,
            'paperFormat': shipment.carrier.dpd_paper_format,
            }

    def shipping_party(self, party, address, usage=None):
        shipping_party = {
            'name1': address.party_full_name[:35],
            'name2': '',
            'street': ' '.join((address.street or '').splitlines())[:35],
            'country': address.country.code if address.country else '',
            'zipCode': address.postal_code[:9],
            'city': address.city[:35],
            }
        if party.full_name != address.party_full_name:
            shipping_party['name2'] = party.full_name[:35]

        phone = party.contact_mechanism_get({'phone', 'mobile'}, usage=usage)
        if phone and len(phone.value) <= 30:
            shipping_party['phone'] = phone.value
        email = party.contact_mechanism_get('email', usage=usage)
        if email and len(email.value) <= 50:
            shipping_party['email'] = email.value

        return shipping_party

    def get_parcel(self, package):
        pool = Pool()
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')

        cm = UoM(ModelData.get_id('product', 'uom_centimeter'))

        parcel = {}

        if package.total_weight:
            # in grams rounded in 10 gram units
            weight = int(package.total_weight * 10) * 10
            if weight < 1000000000:
                parcel['weight'] = weight

        if (package.length is not None
                and package.width is not None
                and package.height is not None):
            length = UoM.compute_qty(
                package.length_uom, package.length, cm)
            width = UoM.compute_qty(
                package.width_uom, package.width, cm)
            height = UoM.compute_qty(
                package.height_uom, package.height, cm)
            if length < 1000 and width < 1000 and height < 1000:
                parcel['volume'] = int(
                    '%03i%03i%03i' % (length, width, height))

        return parcel

    def get_shipment_data(self, credential, shipment, packages):
        return {
            'generalShipmentData': {
                'identificationNumber': shipment.number,
                'sendingDepot': credential.depot,
                'product': shipment.carrier.dpd_product,
                'sender': self.shipping_party(
                    shipment.company.party,
                    shipment.shipping_warehouse.address),
                'recipient': self.shipping_party(
                    shipment.shipping_to, shipment.shipping_to_address),
                },
            'parcels': [self.get_parcel(p) for p in packages],
            'productAndServiceData': {
                'orderType': 'consignment',
                }
            }
