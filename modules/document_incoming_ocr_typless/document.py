# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import base64
from decimal import Decimal
from functools import wraps

import requests

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from .exceptions import TyplessError

MIME_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/tiff',
    }
EXTRACT_DATA = 'https://developers.typless.com/api/extract-data'
ADD_DOCUMENT_FEEDBACK = (
    'https://developers.typless.com/api/add-document-feedback')


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

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('typless', "Typless"))

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

    def _get_supplier_invoice_typless(self, document):
        invoice_data = {}
        if not document.parsed_data:
            return invoice_data
        fields = document.parsed_data.get('extracted_fields', [])
        for name in [
                'company_name', 'company_tax_identifier', 'supplier_name',
                'tax_identifier', 'currency', 'number', 'description',
                'invoice_date', 'payment_term_date', 'total_amount',
                'purchase_orders']:
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
        for name in [
                'product_name', 'description', 'unit', 'quantity',
                'unit_price', 'amount', 'purchase_order']:
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
        fields = document.parsed_data.get('extracted_fields', [])
        learning_fields = []
        getter = getattr(self, f'_typless_feedback_payload_{document.type}')
        for field in fields:
            name = field['name']
            value = getter(source, name)
            if value is None:
                value = get_best_value(fields, name)
            learning_fields.append({
                    'name': name,
                    'value': value,
                    })
        payload = {
            'document_type_name': self.typless_document_type,
            'document_object_id': document.parsed_data['object_id'],
            'learning_fields': learning_fields,
            }
        line_items = document.parsed_data.get('line_items')
        if line_items is not None:
            lines = []
            getter = getattr(
                self, f'_typless_feedback_payload_line_items_{document.type}')
            for i, line_item in enumerate(line_items):
                line = []
                for field in line_item:
                    name = field['name']
                    value = getter(i, name, source)
                    if value is None:
                        value = get_best_value(line_item, name)
                    line.append({
                            'name': name,
                            'value': value,
                            })
                lines.append(line)
            payload['line_items'] = lines
        vat_rates = document.parsed_data.get('vat_rates')
        if vat_rates is not None:
            taxes = []
            getter = getattr(
                self, f'_typless_feedback_payload_vat_rates_{document.type}')
            for i, vat_rate in enumerate(vat_rates):
                percentage = getter(i, 'vat_rate_percentage', source)
                if percentage is None:
                    percentage = get_best_value(
                        vat_rate, 'vat_rate_percentage')
                net = getter(i, 'vat_rate_net', source)
                if net is None:
                    net = get_best_value(vat_rate, 'vat_rate_net')
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
            self, index, name, document):
        pass

    def _typless_feedback_payload_vat_rates_document_incoming(
            self, index, name, document):
        pass

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
        elif name == 'untaxed_amount':
            return str(invoice.untaxed_amount)
        elif name == 'tax_amount':
            return str(invoice.tax_amount)
        elif name == 'total_amount':
            return str(invoice.total_amount)
        elif name == 'purchase_orders':
            return invoice.origins

    def _typless_feedback_payload_line_items_supplier_invoice(
            self, index, name, invoice):
        lines = [l for l in invoice.lines if l.type == 'line']
        try:
            line = lines[index]
        except IndexError:
            return ''
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
            self, index, name, invoice):
        try:
            line = invoice.taxes[index]
        except IndexError:
            return ''
        if name == 'vat_rate_percentage':
            if line.tax and line.tax.type == 'percentage':
                return str(line.tax.rate * 100)
            else:
                return ''
        elif name == 'vat_rate_net':
            return str(line.base)
