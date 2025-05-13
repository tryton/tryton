# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import bisect
import datetime as dt
import logging
import re
from decimal import Decimal
from operator import itemgetter

from trytond.cache import Cache
from trytond.model import (
    MatchMixin, ModelSQL, ModelView, Workflow, fields, sequence_ordered)
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

logger = logging.getLogger(__name__)


class Incoming(metaclass=PoolMeta):
    __name__ = 'document.incoming'

    ocr_service = fields.Many2One(
        'document.incoming.ocr.service', "OCR Service", readonly=True,
        states={
            'invisible': ~Eval('ocr_service'),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            ocr_send_feedback={
                'invisible': ~Eval('ocr_service') | (Eval('state') != 'done'),
                'depends': ['ocr_service', 'state'],
                },
            )

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def proceed(cls, documents, with_children=False):
        pool = Pool()
        Service = pool.get('document.incoming.ocr.service')
        for document in documents:
            service = Service.get_service(document)
            if service:
                document.ocr_service = service
                document.parsed_data = service.process(document)
        cls.save(documents)
        super().proceed(documents, with_children=with_children)

    def _process_document_incoming(self):
        document = super()._process_document_incoming()
        if self.ocr_service:
            document_data = self.ocr_service.get_document_incoming(self)
            document_type = document_data.get('document_type')
            if (document_type
                    and document_type in dict(self.__class__.type.selection)):
                document.type = document_type
        return document

    @classmethod
    @ModelView.button
    def ocr_send_feedback(cls, documents):
        for document in documents:
            if document.ocr_service:
                document.ocr_service.send_feedback(document)

    @classmethod
    def copy(cls, documents, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('ocr_service')
        return super().copy(documents, default=default)


class IncomingSupplierInvoice(metaclass=PoolMeta):
    __name__ = 'document.incoming'

    def _process_supplier_invoice(self):
        pool = Pool()
        Party = pool.get('party.party')
        Currency = pool.get('currency.currency')

        invoice = super()._process_supplier_invoice()
        if self.ocr_service:
            invoice_data = self.ocr_service.get_supplier_invoice(self)

            tax_identifier = invoice_data.get('tax_identifier')
            if tax_identifier and invoice.party:
                tax_identifier_types = Party.tax_identifier_types()
                for identifier in invoice.party.identifiers:
                    if (identifier.type in tax_identifier_types
                            and identifier.code == tax_identifier):
                        invoice.party_tax_identifier = identifier

            currency = invoice_data.get('currency')
            if currency:
                try:
                    invoice.currency, = Currency.search([
                            ('code', '=', currency),
                            ])
                except ValueError:
                    logger.debug(f"Cannot find currency '{currency}'")

            invoice.reference = invoice_data.get('number')
            invoice.description = invoice_data.get('description')

            invoice_date = invoice_data.get('invoice_date')
            if invoice_date:
                try:
                    invoice.invoice_date = dt.date.fromisoformat(invoice_date)
                except ValueError:
                    logger.debug(f"Cannot parse invoice date '{invoice_date}'")

            payment_term_date = invoice_data.get('payment_term_date')
            if payment_term_date:
                try:
                    invoice.payment_term_date = dt.date.fromisoformat(
                        payment_term_date)
                    invoice.payment_term = None
                except ValueError:
                    logger.debug(
                        "Cannot parse payment term date "
                        f"'{payment_term_date}'")

            lines = []
            for parsed_line in invoice_data.get('lines', []):
                line = self._process_supplier_invoice_line(
                    invoice, parsed_line, invoice_data)
                if line:
                    lines.append(line)
            if not lines:
                line_data = self._process_supplier_invoice_line_single(
                    invoice, invoice_data)
                if line_data:
                    line = self._process_supplier_invoice_line(
                        invoice, line_data, invoice_data)
                    if line:
                        lines.append(line)
            invoice.lines = lines

            taxes = []
            for parsed_tax in invoice_data.get('taxes', []):
                tax = self._process_supplier_invoice_tax(
                    invoice, parsed_tax)
                if tax:
                    taxes.append(tax)
            if taxes:
                for line in invoice.lines:
                    line.taxes = None
            invoice.taxes = taxes

        return invoice

    def _process_supplier_invoice_line_single(self, invoice, invoice_data):
        total_amount = invoice_data.get('total_amount')
        if total_amount:
            return {'quantity': 1, 'amount': total_amount}

    def _process_supplier_invoice_line(self, invoice, line_data, invoice_data):
        from trytond.modules.product import round_price
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')
        InvoiceLine = pool.get('account.invoice.line')
        Product = pool.get('product.product')
        UoM = pool.get('product.uom')

        account_configuration = AccountConfiguration(1)

        line = InvoiceLine(
            invoice=invoice,
            currency=invoice.currency,
            company=invoice.company)
        product_name = line_data.get('product_name')
        if product_name:
            try:
                product, = Product.search([
                        ('rec_name', 'ilike', product_name),
                        ])
            except ValueError:
                logger.debug(f"Cannot find product '{product_name}'")
                line.product = None
            else:
                line.product = product.id
                line.on_change_product()
        else:
            line.product = None
        line.description = line_data.get('description')
        if not line.product:
            if line.description:
                similar_lines = InvoiceLine.search([
                        ('description', 'ilike', line.description),
                        ('invoice.company', '=', invoice.company),
                        ('invoice.type', '=', invoice.type),
                        ('invoice.state', 'in',
                            ['validated', 'posted', 'paid']),
                        ],
                    order=[('invoice.invoice_date', 'DESC')],
                    limit=1)
            else:
                similar_lines = []
            if similar_lines:
                similar_line, = similar_lines
                line.account = similar_line.account
                line.product = similar_line.product
                line.unit = similar_line.unit
                line.taxes = similar_line.taxes
            else:
                line.account = account_configuration.get_multivalue(
                    'default_category_account_expense',
                    company=invoice.company.id)
                line.on_change_account()

        unit = line_data.get('unit')
        if unit:
            try:
                unit, = UoM.search([
                        ('rec_name', 'ilike', unit),
                        ])
            except ValueError:
                logger.debug(f"Cannot find UoM '{unit}'")
            else:
                if (not line.product
                        or line.product.default_uom.category == unit.category):
                    line.unit = unit

        quantity = line_data.get('quantity') or 0
        if getattr(line, 'unit', None):
            quantity = line.unit.round(quantity)
        line.quantity = quantity or 1

        unit_price = line_data.get('unit_price')
        amount = line_data.get('amount')
        if unit_price is not None:
            line.unit_price = round_price(unit_price)
        elif amount is not None:
            line.unit_price = round_price(
                amount / Decimal(str(line.quantity)))
        else:
            line.unit_price = 0
        return line

    def _process_supplier_invoice_tax(self, invoice, parsed_tax):
        pool = Pool()
        Tax = pool.get('account.tax')
        InvoiceTax = pool.get('account.invoice.tax')

        invoice_tax = InvoiceTax(invoice=invoice, manual=True)

        try:
            tax, = Tax.search([
                    ['OR',
                        ('group', '=', None),
                        ('group.kind', 'in', ['purchase', 'both']),
                        ],
                    ('company', '=', invoice.company.id),
                    ('type', '=', parsed_tax.get('type')),
                    ('amount', '=', parsed_tax.get('amount')),
                    ('rate', '=', parsed_tax.get('rate')),
                    ])
        except ValueError:
            logger.debug(f"Cannot find tax for '{parsed_tax}'")
            return
        invoice_tax.tax = tax.id
        invoice_tax.on_change_tax()

        base = parsed_tax.get('base')
        if base is not None:
            invoice_tax.base = invoice.currency.round(base)
            invoice_tax.on_change_base()
        else:
            amount = parsed_tax.get('amount') or 0
            invoice_tax.base = 0
            invoice_tax.amount = invoice_tax.currency.round(amount)
        return invoice_tax

    @property
    def supplier_invoice_company(self):
        pool = Pool()
        Company = pool.get('company.company')
        Party = pool.get('party.party')
        Identifier = pool.get('party.identifier')

        company = super().supplier_invoice_company

        if self.ocr_service:
            invoice_data = self.ocr_service.get_supplier_invoice(self)

            company_name = invoice_data.get('company_name')
            if company_name:
                try:
                    company, = Company.search([
                            ('party.rec_name', 'ilike', company_name),
                            ])
                except ValueError:
                    logger.debug(f"Cannot find company '{company_name}'")

            tax_identifier = invoice_data.get('company_tax_identifier')
            if tax_identifier:
                identifiers = Identifier.search([
                        ('code', '=', tax_identifier),
                        ('type', 'in', Party.tax_identifier_types()),
                        ])
                if len(identifiers) == 1:
                    identifier, = identifiers
                    try:
                        company, = Company.search([
                                ('party', '=', identifier.party.id),
                                ])
                    except ValueError:
                        logger.debug(
                            "Cannot find company for party "
                            f"'{identifier.party.id}'")
                else:
                    logger.debug(f"Cannot find company '{tax_identifier}'")
        return company

    @property
    def supplier_invoice_party(self):
        pool = Pool()
        Party = pool.get('party.party')
        Identifier = pool.get('party.identifier')

        party = super().supplier_invoice_party

        if self.ocr_service:
            invoice_data = self.ocr_service.get_supplier_invoice(self)

            supplier_name = invoice_data.get('supplier_name')
            if supplier_name:
                try:
                    party, = Party.search([
                            ('rec_name', 'ilike', supplier_name),
                            ])
                except ValueError:
                    logger.debug(f"Cannot find party '{supplier_name}'")

            tax_identifier = invoice_data.get('tax_identifier')
            if tax_identifier:
                identifiers = Identifier.search([
                        ('code', '=', tax_identifier),
                        ('type', 'in', Party.tax_identifier_types()),
                        ])
                if len(identifiers) == 1:
                    identifier, = identifiers
                    party = identifier.party
                else:
                    logger.debug(f"Cannot find party '{tax_identifier}'")
        return party


class IncomingSupplierInvoicePurchase(metaclass=PoolMeta):
    __name__ = 'document.incoming'

    def _process_supplier_invoice_line(self, invoice, line_data):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        UoM = pool.get('product.uom')

        line = super()._process_supplier_invoice_line(invoice, line_data)

        if (line and line.product and line.unit
                and (line_data.get('purchase_orders')
                    or line_data.get('purchase_order'))):
            if line_data.get('purchase_order'):
                numbers = [line_data['purchase_order']]
            else:
                numbers = re.split(r'[ ,;]', line_data['purchase_orders'])
            purchase_lines = PurchaseLine.search([
                    ('purchase.company', '=', invoice.company),
                    ('purchase.rec_name', 'in', numbers),
                    ('type', '=', 'line'),
                    ('product', '=', line.product.id),
                    ])
            if purchase_lines:
                quantities = []
                for purchase_line in purchase_lines:
                    quantity = UoM.compute_qty(
                        purchase_line.unit, purchase_line.quantity, line.unit)
                    quantities.append((quantity, purchase_line))
                key = itemgetter(0)
                quantities.sort(key=key)
                index = bisect.bisect_left(quantities, line.quantity, key=key)
                if index >= len(quantities):
                    index = -1
                line.origin = str(quantities[index][1])
        return line


class IncomingOCRService(sequence_ordered(), ModelSQL, ModelView, MatchMixin):
    __name__ = 'document.incoming.ocr.service'

    type = fields.Selection([
            (None, ''),
            ], "Type")
    company = fields.Many2One(
        'company.company', "Company",
        help="The company for which the service is used.\n"
        "Leave empty for any company.")
    source = fields.Char(
        "Source",
        help="The regular expression to match the document source.\n"
        "Leave empty to allow any source.")
    document_type = fields.Selection(
        'get_document_types', "Type",
        help="The document type to match.\n"
        "Leave empty for any type.")
    _get_service_cache = Cache(
        'document.incoming.ocr.service.get_service', context=False)

    @classmethod
    def get_document_types(cls):
        pool = Pool()
        Incoming = pool.get('document.incoming')
        return Incoming.fields_get(['type'])['type']['selection']

    @classmethod
    def get_service(cls, document):
        pattern = cls._get_pattern(document)
        key = tuple(sorted(pattern.items()))
        service_id = cls._get_service_cache.get(key, -1)
        if service_id is None:
            return None
        if service_id >= 0:
            return cls(service_id)
        for service in cls.search([]):
            if service.match(pattern):
                break
        else:
            service = None
        cls._get_service_cache.set(key, service.id if service else None)
        return service

    @classmethod
    def _get_pattern(cls, document):
        return {
            'company': document.company.id if document.company else None,
            'source': document.source or None,
            'document_type': document.type or None,
            'mime_type': document.mime_type,
            }

    def match(self, pattern):
        pattern = pattern.copy()
        source = pattern.pop('source', None)
        if (self.source
                and (not source
                    or not re.search(self.source, source))):
            return False
        if not self.match_mime_type(pattern.pop('mime_type', None)):
            return False
        return super().match(pattern)

    def match_mime_type(self, mime_type):
        return True

    def process(self, document):
        if self.type:
            return getattr(self, f'_process_{self.type}')(document)

    def get_document_incoming(self, document):
        if self.type:
            return getattr(
                self, f'_get_document_incoming_{self.type}')(document)
        else:
            return {}

    def get_supplier_invoice(self, document):
        if self.type:
            return getattr(
                self, f'_get_supplier_invoice_{self.type}')(document)
        else:
            return {}

    def send_feedback(self, document):
        if self.type:
            getattr(self, f'_send_feedback_{self.type}')(document)

    @classmethod
    def on_modification(cls, mode, services, field_names=None):
        super().on_modification(mode, services, field_names=field_names)
        cls._get_service_cache.clear()
