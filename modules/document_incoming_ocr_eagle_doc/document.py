# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import json
from decimal import Decimal
from functools import wraps
from itertools import zip_longest

import requests

from trytond.i18n import gettext
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If

from .exceptions import EagleDocCredentialWarning, EagleDocError

MIME_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/tiff',
    }
INVOICE = 'https://de.eagle-doc.com/api/invoice/v1/processing'
FEEDBACK = 'https://de.eagle-doc.com/api/docu/learning'


def eagle_doc_api(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.HTTPError as e:
            error_message = e.args[0]
            raise EagleDocError(
                gettext('document_incoming_ocr_eagle_doc'
                    '.msg_eagle_doc_webserver_error',
                    message=error_message)) from e
    return wrapper


def get_value(values, name, default=None):
    return values.get(name, {}).get('value', default)


def set_value(values, name, value):
    values.setdefault(name, {})['value'] = str(value)


class IncomingOCRService(metaclass=PoolMeta):
    __name__ = 'document.incoming.ocr.service'

    _states = {
        'required': Eval('type') == 'eagle_doc',
        'invisible': Eval('type') != 'eagle_doc',
        }

    eagle_doc_api_key = fields.Char(
        "API Key", states=_states,
        help="The API key from Eagle Doc app.")
    eagle_doc_endpoint = fields.Selection([
            (None, ""),
            ],
        "Endpoint",
        states=_states)
    eagle_doc_privacy = fields.Boolean(
        "Privacy",
        states={
            'invisible': _states['invisible'],
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.type.selection.append(('eagle_doc', "Eagle Doc"))

    @classmethod
    def default_eagle_doc_privacy(cls):
        return True

    def match_mime_type(self, mime_type):
        match = super().match_mime_type(mime_type)
        if self.type == 'eagle_doc':
            match = mime_type in MIME_TYPES
        return match

    @eagle_doc_api
    def _process_eagle_doc(self, document):
        return getattr(
            self, f'_process_eagle_doc_{self.eagle_doc_endpoint}')(document)

    @eagle_doc_api
    def _send_feedback_eagle_doc(self, document):
        headers = {
            'api-key': self.eagle_doc_api_key,
            }
        response = requests.post(
            FEEDBACK,
            headers=headers,
            files={
                'file': (document.name, document.data, document.mime_type),
                'original': json.dumps(document.parsed_data),
                'corrected': json.dumps(
                    self._eagle_doc_feedback_corrected(document)),
                })
        response.raise_for_status()
        return response.json()

    def _eagle_doc_feedback_corrected(self, document):
        feedback = dict(document.parsed_data)
        return feedback

    @classmethod
    def check_modification(cls, mode, services, values=None, external=False):
        pool = Pool()
        Warning = pool.get('res.user.warning')

        super().check_modification(
            mode, services, values=values, external=external)

        if mode == 'write' and external and 'eagle_doc_api_key' in values:
            warning_name = Warning.format('eagle_doc_credential', services)
            if Warning.check(warning_name):
                raise EagleDocCredentialWarning(
                    warning_name,
                    gettext('document_incoming_ocr_eagle_doc'
                        '.msg_eagle_doc_credential_modified'))


class IncomingOCRService_IncomingInvoice(metaclass=PoolMeta):
    __name__ = 'document.incoming.ocr.service'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.eagle_doc_endpoint.selection.append(('invoice', "Invoice"))
        cls.document_type.domain = [
            cls.document_type.domain,
            [If(Eval('eagle_doc_endpoint') == 'invoice',
                    ('document_type', '=', 'supplier_invoice'),
                    ())],
            ]

    def _process_eagle_doc_invoice(self, document):
        headers = {
            'api-key': self.eagle_doc_api_key,
            }
        response = requests.post(
            INVOICE,
            headers=headers,
            files={
                'file': (document.name, document.data, document.mime_type),
                },
            params={
                'privacy': self.eagle_doc_privacy,
                })
        response.raise_for_status()
        return response.json()

    def _get_supplier_invoice_eagle_doc(self, document):
        invoice_data = {}
        if not document.parsed_data:
            return invoice_data
        general = document.parsed_data.get('general', {})
        invoice_data['company_name'] = (
            get_value(general, 'CustomerCompany')
            or get_value(general, 'CustomerName'))
        invoice_data['supplier_name'] = get_value(general, 'ShopName')
        invoice_data['tax_identifier'] = (
            get_value(general, 'TaxNumber')
            or get_value(general, 'VATNumber')
            or get_value(general, 'CompanyRegistrationNumber'))
        invoice_data['currency'] = get_value(general, 'Currency')
        invoice_data['number'] = get_value(general, 'InvoiceNumber')
        invoice_data['invoice_date'] = get_value(general, 'InvoiceDate')
        invoice_data['payment_term_date'] = (
            get_value(general, 'InvoiceDueDate'))
        invoice_data['total_amount'] = get_value(general, 'TotalPrice')
        invoice_data['purchase_orders'] = get_value(general, 'OrderNumber')

        invoice_data['lines'] = lines = []
        for product_item in document.parsed_data.get('productItems', []):
            lines.append(self._get_supplier_invoice_eagle_doc_line(
                    product_item, invoice_data))

        invoice_data['taxes'] = taxes = []
        for parsed_tax in document.parsed_data.get('taxes', []):
            taxes.append(self._get_supplier_invoice_eagle_doc_tax(
                    parsed_tax, invoice_data))
        return invoice_data

    def _get_supplier_invoice_eagle_doc_line(self, product_item, invoice_data):
        line = {}
        if 'purchase_orders' in invoice_data:
            line['purchase_orders'] = invoice_data['purchase_orders']
        line['product_name'] = get_value(product_item, 'ProductName')
        line['unit'] = get_value(product_item, 'ProductUnit')
        quantity = get_value(product_item, 'ProductQuantity')
        if quantity is not None:
            line['quantity'] = float(quantity)
        unit_price = get_value(product_item, 'ProductUnitPrice')
        if unit_price is not None:
            line['unit_price'] = Decimal(unit_price)
        if (amount := get_value(product_item, 'ProductPrice')) is not None:
            line['amount'] = Decimal(amount)
        line['purchase_order'] = get_value(line, 'OrderNumber')
        return line

    def _get_supplier_invoice_eagle_doc_tax(self, parsed_tax, invoice_data):
        tax = {'type': 'percentage'}
        if (percentage := get_value(parsed_tax, 'TaxPercentage')) is not None:
            tax['rate'] = Decimal(percentage) / 100
        if (net := get_value(parsed_tax, 'TaxNetAmount')) is not None:
            tax['base'] = Decimal(net)
        return tax

    def _eagle_doc_feedback_corrected(self, document):
        feedback = super()._eagle_doc_feedback_corrected(document)
        if self.eagle_doc_endpoint == 'invoice':
            invoice = document.result
            general = feedback.setdefault('general', {})
            set_value(general, 'CustomerCompany', invoice.company.party.name)
            set_value(general, 'ShopName', invoice.party.name)
            set_value(general, 'TaxNumber',
                invoice.party_tax_identifier.code
                if invoice.party_tax_identifier else '')
            set_value(general, 'Currency', invoice.currency.code)
            set_value(general, 'InvoiceNumber', invoice.reference)
            set_value(general, 'InvoiceDate', invoice.invoice_date.isoformat())
            set_value(general, 'InvoiceDueDate',
                invoice.payment_term_date.isoformat()
                if invoice.payment_term_date else '')
            set_value(general, 'TotalPrice', str(invoice.total_amount))
            set_value(general, 'OrderNumber', invoice.origins)
            productItems = list(feedback.get('productItems', []))
            for i, (product_item, line) in enumerate(
                    zip_longest(productItems, invoice.line_lines)):
                if product_item is None:
                    product_item = {}
                    productItems.append(product_item)
                elif line is None:
                    productItems = productItems[:i - 1]
                    break
                set_value(
                    product_item, 'ProductName',
                    line.product.name if line.product else '')
                set_value(
                    product_item, 'ProductUnit',
                    line.unit.name if line.unit else '')
                set_value(product_item, 'ProductQuantity', line.quantity)
                set_value(product_item, 'ProductUnitPrice', line.unit_price)
                set_value(product_item, 'ProductPrice', line.amount)
                set_value(product_item, 'OrderNumber', line.origin_name)
            feedback['productItems'] = productItems
            taxes = list(feedback.get('taxes', []))
            for i, (tax, line) in enumerate(
                    zip_longest(taxes, invoice.taxes)):
                if line.tax and line.tax.type == 'percentage':
                    percentage = line.tax.rate * 100
                else:
                    percentage = ''
                set_value(tax, 'TaxPercentage', percentage)
                set_value(tax, 'TaxNetAmount', line.base)
                set_value(tax, 'TaxAmount', line.amount)
                set_value(tax, 'TaxGrossAmount', line.base + line.amount)
        return feedback
