# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
from decimal import Decimal
from functools import wraps

import requests

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

from .exceptions import TyplessCredentialWarning, TyplessError

MIME_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/tiff',
    }
EXTRACT_DATA = 'https://developers.typless.com/api/extract-data'
ADD_DOCUMENT_FEEDBACK = (
    'https://developers.typless.com/api/add-document-feedback')

SUPPLIER_INVOICE_FIELDS = [
    'company_name',
    'company_tax_identifier',
    'supplier_name',
    'tax_identifier',
    'currency',
    'number',
    'description',
    'invoice_date',
    'payment_term_date',
    'payment_reference',
    'total_amount',
    'untaxed_amount',
    'tax_amount',
    'purchase_orders',
    ]
SUPPLIER_INVOICE_FIELDS = [(x, x) for x in SUPPLIER_INVOICE_FIELDS]
SUPPLIER_INVOICE_LINE_ITEM_FIELDS = [
    'product_name',
    'description',
    'unit',
    'quantity',
    'unit_price',
    'amount',
    'purchase_order',
    ]
SUPPLIER_INVOICE_LINE_ITEM_FIELDS = [
    (x, x) for x in SUPPLIER_INVOICE_LINE_ITEM_FIELDS]


def typless_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            error_message = e.args[0]
        raise TyplessError(
            gettext('document_incoming_ocr_typless'
                '.msg_typless_webserver_error',
                message=error_message))
    return wrapper


def get_best_value(fields, name):
    for field in fields:
        if field.get('name') == name:
            break
    else:
        return
    values = field.get('values', [])
    values = sorted(
        values, key=lambda v: v.get('confidence_score'), reverse=True)
    if values:
        return values[0].get('value')


class IncomingOCRService(metaclass=PoolMeta):
    __name__ = 'document.incoming.ocr.service'

    _states = {
        'required': Eval('type') == 'typless',
        'invisible': Eval('type') != 'typless',
        }

    typless_api_key = fields.Char(
        "API Key", states=_states,
        help="The standard token from Typless settings page.")
    typless_document_type = fields.Char(
        "Document Type", states=_states,
        help="The name of the document type on Typless.")
    typless_fields = fields.MultiSelection(
        'get_typless_fields', "Fields",
        translate=False,
        states={
            'invisible': _states['invisible'],
            },
        help="The metadata fields setup for this document type.")
    typless_line_item_fields = fields.MultiSelection(
        'get_typless_line_item_fields', "Line Item Fields",
        translate=False,
        states={
            'invisible': _states['invisible'],
            },
        help="The line item fields setup for this document type.")
    typless_vat_rates = fields.Boolean(
        "VAT Rates",
        states={
            'invisible': _states['invisible'],
            },
        help="Check if the vat rate net plugin is activated "
        "for this document type.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('typless', "Typless"))

    def get_typless_fields(self):
        return [('document_type', 'document_type')]

    def get_typless_line_item_fields(self):
        return []

    def match_mime_type(self, mime_type):
        match = super().match_mime_type(mime_type)
        if self.type == 'typless':
            match = mime_type in MIME_TYPES
        return match

    @typless_api
    def _process_typless(self, document):
        payload = self._typless_extract_payload(document)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': self.typless_api_key,
            }
        response = requests.post(EXTRACT_DATA, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def _typless_extract_payload(self, document):
        return {
            'file': base64.b64encode(document.data).decode('utf-8'),
            'file_name': document.name,
            'document_type_name': self.typless_document_type,
            }

    def _get_document_incoming_typless(self, document):
        document_data = {}
        if not document.parsed_data:
            return document_data
        fields = document.parsed_data.get('extracted_fields', [])
        document_type = get_best_value(fields, 'document_type')
        if document_type is not None:
            document_data['document_type'] = document_type
        return document_data

    @typless_api
    def _send_feedback_typless(self, document):
        payload = self._typless_feedback_payload(document)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': self.typless_api_key,
            }
        response = requests.post(
            ADD_DOCUMENT_FEEDBACK, json=payload, headers=headers)
        response.raise_for_status()

    def _typless_feedback_payload(self, document):
        source = document.result
        fields = document.ocr_service.typless_fields
        learning_fields = []
        getter = getattr(self, f'_typless_feedback_payload_{document.type}')
        for name in fields:
            value = getter(source, name)
            learning_fields.append({
                    'name': name,
                    'value': value,
                    })
        payload = {
            'document_type_name': self.typless_document_type,
            'document_object_id': document.parsed_data['object_id'],
            'learning_fields': learning_fields,
            }
        line_items = document.ocr_service.typless_line_item_fields
        if line_items:
            lines = []
            getter = getattr(
                self, f'_typless_feedback_payload_line_items_{document.type}')
            for line in source.line_lines:
                line_item = []
                for name in line_items:
                    value = getter(line, name)
                    line_item.append({
                            'name': name,
                            'value': value,
                            })
                lines.append(line_item)
            payload['line_items'] = lines
        if document.ocr_service.typless_vat_rates:
            taxes = []
            getter = getattr(
                self, f'_typless_feedback_payload_vat_rates_{document.type}')
            for tax_line in source.taxes:
                percentage = getter(tax_line, 'vat_rate_percentage')
                net = getter(tax_line, 'vat_rate_net')
                if percentage and net:
                    taxes.append([{
                                'name': 'vat_rate_percentage',
                                'value': percentage,
                                }, {
                                'name': 'vat_rate_net',
                                'value': net,
                                }])
            payload['vat_rates'] = taxes
        return payload

    def _typless_feedback_payload_document_incoming(self, document, name):
        if name == 'document_type':
            return document.type

    def _typless_feedback_payload_line_items_document_incoming(
            self, line, name):
        pass

    def _typless_feedback_payload_vat_rates_document_incoming(
            self, tax_line, name):
        pass

    @classmethod
    def check_modification(cls, mode, services, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        super().check_modification(
            mode, services, values=values, external=external)

        if mode == 'write' and external and 'typless_api_key' in values:
            warning_name = Warning.format('typless_credential', services)
            if Warning.check(warning_name):
                raise TyplessCredentialWarning(
                    warning_name,
                    gettext('document_incoming_ocr_typless'
                        '.msg_typless_credential_modified'))


class IncomingOCRService_IncomingInvoice(metaclass=PoolMeta):
    __name__ = 'document.incoming.ocr.service'

    @fields.depends('document_type')
    def get_typless_fields(self):
        selection = super().get_typless_fields()
        if self.document_type == 'supplier_invoice':
            selection += SUPPLIER_INVOICE_FIELDS
        return selection

    @fields.depends('document_type')
    def get_typless_line_item_fields(self):
        selection = super().get_typless_line_item_fields()
        if self.document_type == 'supplier_invoice':
            selection += SUPPLIER_INVOICE_LINE_ITEM_FIELDS
        return selection

    def _get_supplier_invoice_typless(self, document):
        invoice_data = {}
        if not document.parsed_data:
            return invoice_data
        fields = document.parsed_data.get('extracted_fields', [])
        for name in self.typless_fields:
            value = get_best_value(fields, name)
            if value is not None:
                if name == 'total_amount':
                    value = Decimal(value)
                invoice_data[name] = value
        invoice_data['lines'] = lines = []
        for parsed_line in document.parsed_data.get('line_items', []):
            lines.append(self._get_supplier_invoice_typless_line(
                    parsed_line, invoice_data))
        invoice_data['taxes'] = taxes = []
        for parsed_tax in document.parsed_data.get('vat_rates', []):
            taxes.append(self._get_supplier_invoice_typless_tax(
                    parsed_tax, invoice_data))
        return invoice_data

    def _get_supplier_invoice_typless_line(self, parsed_line, invoice_data):
        line = {}
        if 'purchase_orders' in invoice_data:
            line['purchase_orders'] = invoice_data['purchase_orders']
        for name in self.typless_line_item_fields:
            value = get_best_value(parsed_line, name)
            if value is not None:
                if name in {'unit_price', 'amount'}:
                    value = Decimal(value)
                elif name == 'quantity':
                    value = float(value)
                line[name] = value
        return line

    def _get_supplier_invoice_typless_tax(sef, parsed_tax, invoice_data):
        tax = {'type': 'percentage'}
        percentage = get_best_value(parsed_tax, 'vat_rate_percentage')
        if percentage is not None:
            tax['rate'] = Decimal(percentage) / 100
        net = get_best_value(parsed_tax, 'vat_rate_net')
        if net is not None:
            tax['base'] = Decimal(net)
        return tax

    def _typless_feedback_payload_supplier_invoice(self, invoice, name):
        if name == 'company_name':
            return invoice.company.party.name
        elif name == 'company_tax_identifier':
            if invoice.tax_identifier:
                return invoice.tax_identifier.code
            else:
                return ''
        elif name == 'supplier_name':
            return invoice.party.name
        elif name == 'tax_identifier':
            if invoice.party_tax_identifier:
                return invoice.party_tax_identifier.code
            else:
                return ''
        elif name == 'currency':
            return invoice.currency.code
        elif name == 'number':
            return invoice.reference
        elif name == 'description':
            return invoice.description
        elif name == 'invoice_date':
            return invoice.invoice_date.isoformat()
        elif name == 'payment_term_date':
            if invoice.payment_term_date:
                return invoice.payment_term_date.isoformat()
            else:
                return ''
        elif name == 'payment_reference':
            return invoice.supplier_payment_reference
        elif name == 'untaxed_amount':
            return str(invoice.untaxed_amount)
        elif name == 'tax_amount':
            return str(invoice.tax_amount)
        elif name == 'total_amount':
            return str(invoice.total_amount)
        elif name == 'purchase_orders':
            return invoice.origins

    def _typless_feedback_payload_line_items_supplier_invoice(
            self, line, name):
        if name == 'product_name':
            if line.product:
                return line.product.name
            else:
                return ''
        elif name == 'description':
            return line.description
        elif name == 'unit':
            if line.unit:
                return line.unit.name
            else:
                return ''
        elif name == 'quantity':
            return str(line.quantity)
        elif name == 'unit_price':
            return str(line.unit_price)
        elif name == 'amount':
            return str(line.amount)
        elif name == 'purchase_order':
            return line.origin_name

    def _typless_feedback_payload_vat_rates_supplier_invoice(
            self, tax_line, name):
        if name == 'vat_rate_percentage':
            if tax_line.tax and tax_line.tax.type == 'percentage':
                return str(tax_line.tax.rate * 100)
            else:
                return ''
        elif name == 'vat_rate_net':
            return str(tax_line.base)
