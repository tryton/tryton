# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import bisect
import datetime as dt
import mimetypes
import os
from base64 import b64decode, b64encode
from decimal import Decimal
from io import BytesIO
from itertools import chain, groupby
from operator import itemgetter

import genshi
import genshi.template
# XXX fix: https://genshi.edgewall.org/ticket/582
from genshi.template.astutil import ASTCodeGenerator, ASTTransformer
from lxml import etree

from trytond.i18n import gettext
from trytond.model import Model
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.tools import cached_property, slugify
from trytond.transaction import Transaction

from .exceptions import InvoiceError
from .party import ISO6523_TYPES

ISO6523 = {v: k for k, v in ISO6523_TYPES.items()}

if not hasattr(ASTCodeGenerator, 'visit_NameConstant'):
    def visit_NameConstant(self, node):
        if node.value is None:
            self._write('None')
        elif node.value is True:
            self._write('True')
        elif node.value is False:
            self._write('False')
        else:
            raise Exception("Unknown NameConstant %r" % (node.value,))
    ASTCodeGenerator.visit_NameConstant = visit_NameConstant
if not hasattr(ASTTransformer, 'visit_NameConstant'):
    # Re-use visit_Name because _clone is deleted
    ASTTransformer.visit_NameConstant = ASTTransformer.visit_Name

loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Invoice(Model):
    __name__ = 'edocument.ubl.invoice'
    __slots__ = ('invoice',)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'render': RPC(instantiate=0),
                'parse': RPC(readonly=False, result=int),
                })

    def __init__(self, invoice):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        super().__init__()
        if int(invoice) >= 0:
            invoice = Invoice(int(invoice))
            with Transaction().set_context(language=invoice.party_lang):
                self.invoice = invoice.__class__(int(invoice))
        else:
            self.invoice = invoice

    def render(self, template, specification=None):
        if self.invoice.state not in {'posted', 'paid'}:
            raise ValueError("Invoice must be posted")
        tmpl = self._get_template(template)
        if not tmpl:
            raise NotImplementedError
        return (tmpl.generate(this=self, specification=specification)
            .filter(remove_comment)
            .render()
            .encode('utf-8'))

    def _get_template(self, version):
        if self.invoice.sequence_type == 'credit_note':
            return loader.load(os.path.join(version, 'CreditNote.xml'))
        else:
            return loader.load(os.path.join(version, 'Invoice.xml'))

    @property
    def filename(self):
        return f'{slugify(self.invoice.rec_name)}.xml'

    @cached_property
    def type_code(self):
        if self.invoice.type == 'out':
            if self.invoice.sequence_type == 'credit_note':
                return '381'
            else:
                return '380'
        else:
            return '389'

    @property
    def additional_documents(self):
        pool = Pool()
        InvoiceReport = pool.get('account.invoice', type='report')
        oext, content, _, filename = InvoiceReport.execute(
            [self.invoice.id], {})
        filename = f'{filename}.{oext}'
        mimetype = mimetypes.guess_type(filename)[0]
        yield {
            'id': self.invoice.number,
            'type': 'binary',
            'binary': b64encode(content).decode(),
            'mimetype': mimetype,
            'filename': filename,
            }

    @cached_property
    def accounting_supplier_party(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party
        else:
            return self.invoice.party

    @cached_property
    def accounting_supplier_address(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party.address_get('invoice')
        else:
            return self.invoice.invoice_address

    @cached_property
    def accounting_supplier_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.tax_identifier
        else:
            return self.invoice.party_tax_identifier

    @cached_property
    def accounting_customer_party(self):
        if self.invoice.type == 'out':
            return self.invoice.party
        else:
            return self.invoice.company.party

    @cached_property
    def accounting_customer_address(self):
        if self.invoice.type == 'out':
            return self.invoice.invoice_address
        else:
            return self.invoice.company.party.address_get('invoice')

    @cached_property
    def accounting_customer_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.party_tax_identifier
        else:
            return self.invoice.tax_identifier

    @property
    def taxes(self):
        def key(line):
            return line.tax.group
        for group, lines in groupby(
                sorted(self.invoice.taxes, key=key), key=key):
            lines = list(lines)
            amount = sum(l.amount for l in lines)
            yield group, lines, amount

    @cached_property
    def lines(self):
        return [l for l in self.invoice.lines if l.type == 'line']

    @classmethod
    def parse(cls, document):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        tree = etree.parse(BytesIO(document))
        root = tree.getroot()
        namespace = root.nsmap.get(None)
        invoice, attachments = cls.parser(namespace)(root)
        invoice.save()
        invoice.update_taxes()
        cls.checker(namespace)(root, invoice)
        attachments = list(attachments)
        for attachment in attachments:
            attachment.resource = invoice
        Attachment.save(attachments)
        return invoice

    @classmethod
    def parser(cls, namespace):
        return {
            'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2': (
                cls._parse_invoice_2),
            'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2': (
                cls._parse_credit_note_2),
            }.get(namespace)

    @classmethod
    def checker(cls, namespace):
        return {
            'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2': (
                cls._check_invoice_2),
            'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2': (
                cls._check_credit_note_2),
            }.get(namespace)

    @classmethod
    def _parse_invoice_2(cls, root):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')

        type_code = root.findtext('./{*}InvoiceTypeCode')
        if type_code and type_code != '380':
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_invoice_type_code_unsupported',
                    type_code=type_code))

        invoice = Invoice(type='in')
        invoice.reference = root.findtext('./{*}ID')
        invoice.invoice_date = dt.date.fromisoformat(
            root.findtext('./{*}IssueDate'))
        invoice.party = cls._parse_2_supplier(
            root.find('./{*}AccountingSupplierParty'), create=True)
        invoice.set_journal()
        invoice.on_change_party()
        invoice.invoice_address = cls._parse_2_address(
            root.find(
                './{*}AccountingSupplierParty/{*}Party/{*}PostalAddress'),
            party=invoice.party)
        invoice.party_tax_identifier = cls._parse_2_tax_identifier(
            root.findall(
                './{*}AccountingSupplierParty/{*}Party/{*}PartyTaxScheme'),
            party=invoice.party, create=True)
        if (seller := root.find('./{*}SellerSupplierParty')) is not None:
            supplier = cls._parse_2_supplier(seller)
        else:
            supplier = invoice.party
        if (customer_party := root.find('./{*}AccountingCustomerParty')
                ) is not None:
            invoice.company = cls._parse_2_company(customer_party)
        else:
            invoice.company = Invoice.default_company()
        if not invoice.company:
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_company_not_found',
                    company=etree.tostring(
                        customer_party, pretty_print=True).decode()
                    if customer_party else ''))

        if (payee_party := root.find('./{*}PayeeParty')) is not None:
            party = cls._parse_2_party(payee_party)
            if not party:
                party = cls._create_2_party(payee_party)
                party.save()
            invoice.alternative_payees = [party]

        currency_code = root.findtext('./{*}DocumentCurrencyCode')
        if not currency_code:
            payable_amount = root.find(
                './{*}LegalMonetaryTotal/{*}PayableAmount')
            currency_code = payable_amount.get('currencyID')
        if currency_code is not None:
            try:
                invoice.currency, = Currency.search([
                        ('code', '=', currency_code),
                        ], limit=1)
            except ValueError:
                raise InvoiceError(gettext(
                        'edocument_ubl.msg_currency_not_found',
                        code=currency_code))

        invoice.payment_term_date = cls._parse_2_payment_term_date(
            root.findall('./{*}PaymentTerms'))
        invoice.lines = [
            cls._parse_invoice_2_line(
                line, company=invoice.company, currency=invoice.currency,
                supplier=supplier)
            for line in root.iterfind('./{*}InvoiceLine')]
        invoice.taxes = [
            cls._parse_2_tax(
                tax, company=invoice.company)
            for tax in root.iterfind('./{*}TaxTotal/{*}TaxSubtotal')]

        if (hasattr(Invoice, 'cash_rounding')
                and (root.find(
                    './{*}LegalMonetaryTotal/{*}PayableRoundingAmount')
                    is not None)):
            invoice.cash_rounding = True
        return invoice, cls._parse_2_attachments(root)

    @classmethod
    def _parse_invoice_2_line(
            cls, invoice_line, company, currency, supplier=None):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        UoM = pool.get('product.uom')
        Tax = pool.get('account.tax')
        AccountConfiguration = pool.get('account.configuration')

        account_configuration = AccountConfiguration(1)

        line = Line(type='line', company=company, currency=currency)
        if (invoiced_quantity := invoice_line.find('./{*}InvoicedQuantity')
                ) is not None:
            line.quantity = float(invoiced_quantity.text)
            if (unit_code := invoiced_quantity.get('unitCode')) is not None:
                try:
                    line.unit, = UoM.search([
                            ('unece_code', '=', unit_code),
                            ], limit=1)
                except ValueError:
                    raise InvoiceError(gettext(
                            'edocument_ubl.msg_unit_not_found',
                            code=unit_code))
        else:
            line.quantity = 1
            line.unit = None

        line.product = cls._parse_2_item(
            invoice_line.find('./{*}Item'), supplier=supplier)
        if line.product:
            line.on_change_product()

        line.description = '\n'.join(e.text for e in chain(
                invoice_line.iterfind('./{*}Item/{*}Name'),
                invoice_line.iterfind('./{*}Item/{*}BrandName'),
                invoice_line.iterfind('./{*}Item/{*}ModelName'),
                invoice_line.iterfind('./{*}Item/{*}Description'),
                invoice_line.iterfind(
                    './{*}Item/{*}AdditionalInformation'),
                invoice_line.iterfind('./{*}Item/{*}WarrantyInformation'),
                ) if e is not None and e.text)

        if not line.product:
            if line.description:
                similar_lines = Line.search([
                        ('description', 'ilike', line.description),
                        ('invoice.company', '=', company),
                        ('invoice.type', '=', 'in'),
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
                if not line.unit:
                    line.unit = similar_line.unit
            else:
                line.account = account_configuration.get_multivalue(
                    'default_category_account_expense',
                    company=company.id)

        for line_reference in invoice_line.iterfind('./{*}OrderLineReference'):
            line.origin = cls._parse_2_line_reference(
                line_reference, line, company, supplier=supplier)
            if line.origin:
                break

        if (price_amount := invoice_line.findtext('./{*}Price/{*}PriceAmount')
                ) is not None:
            line.unit_price = round_price(Decimal(price_amount))
        else:
            line.unit_price = round_price(
                Decimal(invoice_line.findtext('./{*}LineExtensionAmount'))
                / Decimal(str(line.quantity)))

        if invoice_line.find('./{*}Item/{*}ClassifiedTaxCategory') is not None:
            tax_categories = invoice_line.iterfind(
                './{*}Item/{*}ClassifiedTaxCategory')
        else:
            tax_categories = invoice_line.iterfind(
                './{*}TaxTotal/{*}TaxSubtotal/{*}TaxCategory')
        taxes = []
        for tax_category in tax_categories:
            domain = cls._parse_2_tax_category(tax_category)
            domain.extend([
                    ['OR',
                        ('group', '=', None),
                        ('group.kind', 'in', ['purchase', 'both']),
                        ],
                    ('company', '=', company.id),
                    ])
            try:
                tax, = Tax.search(domain, limit=1)
            except ValueError:
                raise InvoiceError(gettext(
                        'edocument_ubl.msg_tax_not_found',
                        tax_category=etree.tostring(
                            tax_category, pretty_print=True).decode()))
            taxes.append(tax)
        line.taxes = taxes
        return line

    @classmethod
    def _parse_credit_note_2(cls, root):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')

        type_code = root.findtext('./{*}CreditNoteTypeCode')
        if type_code and type_code != '381':
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_credit_note_type_code_unsupported',
                    type_code=type_code))

        invoice = Invoice(type='in')
        invoice.reference = root.findtext('./{*}ID')
        invoice.invoice_date = dt.date.fromisoformat(
            root.findtext('./{*}IssueDate'))
        invoice.party = cls._parse_2_supplier(
            root.find('./{*}AccountingSupplierParty'), create=True)
        invoice.set_journal()
        invoice.on_change_party()
        if (seller := root.find('./{*}SellerSupplierParty')) is not None:
            supplier = cls._parse_2_supplier(seller)
        else:
            supplier = invoice.party
        if (customer_party := root.find('./{*}AccountingCustomerParty')
                ) is not None:
            invoice.company = cls._parse_2_company(customer_party)
        else:
            invoice.company = Invoice.default_company()
        if (payee_party := root.find('./{*}PayeeParty')) is not None:
            party = cls._parse_2_party(payee_party)
            if not party:
                party = cls._create_2_party(payee_party)
                party.save()
            invoice.alternative_payees = [party]
        if (currency_code := root.findtext('./{*}DocumentCurrencyCode')
                ) is not None:
            try:
                invoice.currency, = Currency.search([
                        ('code', '=', currency_code),
                        ], limit=1)
            except ValueError:
                raise InvoiceError(gettext(
                        'edocument_ubl.msg_currency_not_found',
                        code=currency_code))
        invoice.payment_term_date = cls._parse_2_payment_term_date(
            root.findall('./{*}PaymentTerms'))
        invoice.lines = [
            cls._parse_credit_note_2_line(
                line, company=invoice.company, currency=invoice.currency,
                supplier=supplier)
            for line in root.iterfind('./{*}CreditNoteLine')]
        invoice.taxes = [
            cls._parse_2_tax(
                tax, company=invoice.company)
            for tax in root.iterfind('./{*}TaxTotal/{*}TaxSubtotal')]

        if (hasattr(Invoice, 'cash_rounding')
                and root.find(
                    './{*}LegalMonetaryTotal/{*}PayableRoundingAmount')
                is not None):
            invoice.cash_rounding = True
        return invoice, cls._parse_2_attachments(root)

    @classmethod
    def _parse_credit_note_2_line(
            cls, credit_note_line, company, currency, supplier=None):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        UoM = pool.get('product.uom')
        Tax = pool.get('account.tax')
        AccountConfiguration = pool.get('account.configuration')

        account_configuration = AccountConfiguration(1)

        line = Line(type='line', company=company, currency=currency)
        if (credited_quantity := credit_note_line.find('./{*}CreditedQuantity')
                ) is not None:
            line.quantity = -float(credited_quantity.text)
            if (unit_code := credited_quantity.get('unitCode')) is not None:
                try:
                    line.unit, = UoM.search([
                            ('unece_code', '=', unit_code),
                            ], limit=1)
                except ValueError:
                    raise InvoiceError(gettext(
                            'edocument_ubl.msg_unit_not_found',
                            code=unit_code))
        else:
            line.quantity = -1
            line.unit = None

        line.product = cls._parse_2_item(
            credit_note_line.find('./{*}Item'), supplier=supplier)
        if line.product:
            line.on_change_product()

        line.description = '\n'.join(e.text for e in chain(
                credit_note_line.iterfind('./{*}Item/{*}Name'),
                credit_note_line.iterfind('./{*}Item/{*}BrandName'),
                credit_note_line.iterfind('./{*}Item/{*}ModelName'),
                credit_note_line.iterfind('./{*}Item/{*}Description'),
                credit_note_line.iterfind(
                    './{*}Item/{*}AdditionalInformation'),
                credit_note_line.iterfind('./{*}Item/{*}WarrantyInformation'),
                ) if e is not None and e.text)

        if not line.product:
            if line.description:
                similar_lines = Line.search([
                        ('description', 'ilike', line.description),
                        ('invoice.company', '=', company),
                        ('invoice.type', '=', 'in'),
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
                if not line.unit:
                    line.unit = similar_line.unit
            else:
                line.account = account_configuration.get_multivalue(
                    'default_category_account_expense',
                    company=company.id)

        for line_reference in credit_note_line.iterfind(
                './{*}OrderLineReference'):
            line.origin = cls._parse_2_line_reference(
                line_reference, line, company, supplier=supplier)
            if line.origin:
                break

        if (price_amount := credit_note_line.findtext(
                './{*}Price/{*}PriceAmount')) is not None:
            line.unit_price = round_price(Decimal(price_amount))
        else:
            line.unit_price = round_price(
                Decimal(credit_note_line.findtext('./{*}LineExtensionAmount'))
                / line.quantity)

        if (credit_note_line.find('./{*}Item/{*}ClassifiedTaxCategory')
                is not None):
            tax_categories = credit_note_line.iterfind(
                './{*}Item/{*}ClassifiedTaxCategory')
        else:
            tax_categories = credit_note_line.iterfind(
                './{*}TaxTotal/{*}TaxSubtotal/{*}TaxCategory')
        taxes = []
        for tax_category in tax_categories:
            domain = cls._parse_2_tax_category(tax_category)
            domain.extend([
                    ['OR',
                        ('group', '=', None),
                        ('group.kind', 'in', ['purchase', 'both']),
                        ],
                    ('company', '=', company.id),
                    ])
            try:
                tax, = Tax.search(domain, limit=1)
            except ValueError:
                raise InvoiceError(gettext(
                        'edocument_ubl.msg_tax_not_found',
                        tax_category=etree.tostring(
                            tax_category, pretty_print=True).decode()))
            taxes.append(tax)
        line.taxes = taxes
        return line

    @classmethod
    def _parse_2_supplier(cls, supplier_party, create=False):
        pool = Pool()
        Party = pool.get('party.party')
        for account_id in filter(None, chain(
                    [supplier_party.find('./{*}CustomerAssignedAccountID')],
                    supplier_party.iterfind('./{*}AdditionalAccountID'))):
            if account_id.text:
                try:
                    party, = Party.search([
                            ('code', '=', account_id.text),
                            ])
                except ValueError:
                    pass
                else:
                    return party
        party_el = supplier_party.find('./{*}Party')
        party = cls._parse_2_party(party_el)
        if not party and create:
            party = cls._create_2_party(party_el)
            party.save()
        return party

    @classmethod
    def _parse_2_party(cls, party_el):
        pool = Pool()
        Party = pool.get('party.party')

        for identifier in party_el.iterfind('./{*}PartyIdentification/{*}ID'):
            if identifier.text:
                parties = Party.search([
                        ('identifiers.code', '=', identifier.text),
                        ])
                if len(parties) == 1:
                    party, = parties
                    return party

    @classmethod
    def _create_2_party(cls, party_el):
        pool = Pool()
        Party = pool.get('party.party')
        party = Party()
        party.name = party_el.findtext('./{*}PartyName/{*}Name')
        identifiers = []
        for identifier in party_el.iterfind('./{*}PartyIdentification/{*}ID'):
            if identifier.text:
                identifiers.append(cls._create_2_party_identifier(
                        identifier))
        party.identifiers = identifiers
        if (address := party_el.find('./{*}PostalAddress')
                ) is not None:
            party.addresses = [cls._create_2_address(address)]
        return party

    @classmethod
    def _create_2_party_identifier(cls, identifier):
        pool = Pool()
        Identifier = pool.get('party.identifier')
        if schemeId := identifier.get('schemeID'):
            type = ISO6523.get(schemeId)
        else:
            type = None
        return Identifier(type=type, code=identifier.text)

    @classmethod
    def _parse_2_address(cls, address_el, party):
        pool = Pool()
        Address = pool.get('party.address')

        address = cls._create_2_address(address_el)

        domain = [('party', '=', party)]
        for fname in Address._fields:
            if value := getattr(address, fname, None):
                domain.append((fname, '=', value))
        try:
            address, = Address.search(domain, limit=1)
        except ValueError:
            address.party = party
            address.save()
        return address

    @classmethod
    def _create_2_address(cls, address_el):
        pool = Pool()
        Address = pool.get('party.address')
        Country = pool.get('country.country')

        address = Address()

        if address_el is None:
            return address

        address.post_box = address_el.findtext('./{*}Postbox')
        address.floor_number = address_el.findtext('./{*}Floor')
        address.room_number = address_el.findtext('./{*}Room')
        address.street_name = address_el.findtext('./{*}StreetName')
        address.building_name = address_el.findtext('./{*}BuildingName')
        address.building_number = address_el.findtext('./{*}BuildingNumber')
        address.city = address_el.findtext('./{*}CityName')
        address.postal_code = address_el.findtext('./{*}PostalZone')
        if (country_code := address_el.findtext(
                    './{*}Country/{*}IdentificationCode[@listId="ISO3166-1"]')
                ) is not None:
            try:
                country, = Country.search([
                        ('code', '=', country_code),
                        ], limit=1)
            except ValueError:
                pass
            else:
                address.country = country
        address.street_unstructured = '\n'.join(
            (line.text
                for line in address_el.iterfind('./{*}AddressLine/{*}Line')))
        return address

    @classmethod
    def _parse_2_tax_identifier(cls, party_tax_schemes, party, create=False):
        pool = Pool()
        Identifier = pool.get('party.identifier')

        tax_identifier_types = party.tax_identifier_types()

        for party_tax_scheme in party_tax_schemes:
            company_id = party_tax_scheme.find('./{*}CompanyID')
            if company_id is not None:
                scheme_id = company_id.get('schemeID')
                value = company_id.text

                for identifier in party.identifiers:
                    if (identifier.type in tax_identifier_types
                            and identifier.iso_6523 == scheme_id
                            and identifier.code == value):
                        return identifier
                else:
                    if create and scheme_id in ISO6523:
                        identifier = Identifier(
                            party=party,
                            type=ISO6523[scheme_id],
                            code=value)
                        identifier.save()
                        return identifier

    @classmethod
    def _parse_2_company(cls, customer_party):
        pool = Pool()
        Company = pool.get('company.company')
        try:
            CustomerCode = pool.get('party.party.customer_code')
        except KeyError:
            CustomerCode = None

        if CustomerCode:
            for account_id in filter(None, chain(
                        [customer_party.find('./{*}CustomerAssignedAccountID'),
                            customer_party.find(
                                './{*}SupplierAssignedAccountID')],
                        customer_party.iterfind('./{*}AdditionalAccountID'))):
                if account_id.text:
                    try:
                        customer_code, = CustomerCode.search([
                                ('customer_code', '=', account_id.text),
                                ])
                    except ValueError:
                        pass
                    else:
                        return customer_code.company
        for identifier in customer_party.iterfind(
                './{*}Party/{*}PartyIdentification/{*}ID'):
            if identifier.text:
                companies = Company.search([
                        ('party.identifiers.code', '=', identifier.text),
                        ])
                if len(companies) == 1:
                    company, = companies
                    return company

        for company_id in customer_party.iterfind(
                './{*}Party/{*}PartyTaxScheme/{*}CompanyID'):
            companies = Company.search([
                    ('party.identifiers.code', '=', company_id.text),
                    ])
            if len(companies) == 1:
                company, = companies
                return company

        for name in chain(
                customer_party.iterfind(
                    './{*}Party/{*}PartyTaxScheme/{*}RegistrationName'),
                customer_party.iterfind('./{*}Party/{*}PartyName/{*}Name'),
                ):
            if name is None:
                continue
            companies = Company.search([
                    ('party.name', '=', name.text),
                    ])
            if len(companies) == 1:
                company, = companies
                return company

    @classmethod
    def _parse_2_payment_term_date(cls, payment_terms):
        dates = []
        for payment_term in payment_terms:
            if (date := payment_term.findtext('./{*}PaymentDueDate')
                    ) is not None:
                dates.append(dt.date.fromisoformat(date))
        return min(dates, default=None)

    @classmethod
    def _parse_2_item(cls, item, supplier=None):
        pool = Pool()
        Product = pool.get('product.product')

        if (identifier := item.find('./{*}StandardItemIdentification/{*}ID')
                ) is not None:
            if identifier.get('schemeID') == 'GTIN':
                try:
                    product, = Product.search([
                            ('identifiers', 'where', [
                                    ('type', 'in', ['ean', 'isbn', 'ismn']),
                                    ('code', '=', identifier.text),
                                    ]),
                            ], limit=1)
                except ValueError:
                    pass
                else:
                    return product
        if (code := item.findtext('./{*}BuyersItemIdentification/{*}ID')
                ) is not None:
            try:
                product, = Product.search([
                        ('code', '=', code),
                        ], limit=1)
            except ValueError:
                pass
            else:
                return product

    @classmethod
    def _parse_2_line_reference(
            cls, line_reference, line, company, supplier=None):
        return

    @classmethod
    def _parse_2_tax_category(cls, tax_category):
        domain = [
            ('parent', '=', None),
            ]
        if (unece_category_code := tax_category.findtext('./{*}ID')
                ) is not None:
            domain.append(('unece_category_code', '=', unece_category_code))
        if (unece_code := tax_category.findtext('./{*}TaxScheme/{*}ID')
                ) is not None:
            domain.append(('unece_code', '=', unece_code))
        percent = tax_category.findtext('./{*}Percent')
        if percent:
            domain.append(('type', '=', 'percentage'))
            domain.append(('rate', '=', Decimal(percent) / 100))
        return domain

    @classmethod
    def _parse_2_tax(cls, tax, company):
        pool = Pool()
        Tax = pool.get('account.tax')
        InvoiceTax = pool.get('account.invoice.tax')

        invoice_tax = InvoiceTax(manual=False)

        tax_category = tax.find('./{*}TaxCategory')
        domain = cls._parse_2_tax_category(tax_category)
        domain.extend([
                ['OR',
                    ('group', '=', None),
                    ('group.kind', 'in', ['purchase', 'both']),
                    ],
                ('company', '=', company.id),
                ])
        try:
            invoice_tax.tax, = Tax.search(domain, limit=1)
        except ValueError:
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_tax_not_found',
                    tax_category=etree.tostring(
                        tax_category, pretty_print=True).decode()))

        invoice_tax.amount = Decimal(tax.findtext('./{*}TaxAmount'))
        if (taxable_amount := tax.findtext('./{*}TaxableAmount')) is not None:
            invoice_tax.base = Decimal(taxable_amount)
        else:
            # Use tax amount to define the sign of unknown base
            invoice_tax.base = invoice_tax.amount

        invoice_tax.on_change_tax()

        return invoice_tax

    @classmethod
    def _parse_2_attachments(cls, root):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        for name in [
                'DespatchDocumentReference',
                'ReceiptDocumentReference',
                'ContractDocumentReference',
                'AdditionalDocumentReference',
                'StatementDocumentReference',
                'OriginatorDocumentReference'
                ]:
            for document in root.iterfind(f'./{{*}}{name}'):
                attachment = Attachment()
                name = ' '.join(filter(None, [
                            document.findtext('./{*}DocumentType'),
                            document.findtext('./{*}ID'),
                            ]))
                if (data := document.find(
                            './{*}Attachment/{*}EmbeddedDocumentBinaryObject')
                        ) is not None:
                    mime_code = (
                        data.get('mimeCode') or 'application/octet-stream')
                    name += mimetypes.guess_extension(mime_code) or ''
                    attachment.type = 'data'
                    data = b64decode(data.text)
                    attachment.data = data
                elif data := document.findtext(
                        './{*}Attachment/{*}EmbeddedDocument'):
                    name += '.txt'
                    attachment.type = 'data'
                    attachment.data = data
                elif url := document.findtext(
                        './{*}Attachment/{*}ExternalReference/{*}URI'):
                    attachment.type = 'link'
                    Attachment.link = url
                attachment.name = name
                yield attachment

    @classmethod
    def _check_invoice_2(cls, root, invoice):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()

        payable_amount = Decimal(
            root.findtext('./{*}LegalMonetaryTotal/{*}PayableAmount'))
        prepaid_amount = Decimal(
            root.findtext('./{*}LegalMonetaryTotal/{*}PrepaidAmount')
            or 0)
        amount = payable_amount + prepaid_amount
        if not getattr(invoice, 'cash_rounding', False):
            payable_rounding_amount = Decimal(
                root.findtext(
                    './{*}LegalMonetaryTotal/{*}PayableRoundingAmount')
                or 0)
            amount -= payable_rounding_amount
        if invoice.total_amount != amount:
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_invoice_total_amount_different',
                    invoice=invoice.rec_name,
                    total_amount=lang.format_number(invoice.total_amount),
                    amount=lang.format_number(amount)))

        tax_total = sum(Decimal(amount.text) for amount in root.iterfind(
                './{*}TaxTotal/{*}TaxAmount'))
        if invoice.tax_amount != tax_total:
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_invoice_tax_amount_different',
                    invoice=invoice.rec_name,
                    tax_amount=lang.format_number(invoice.tax_amount),
                    tax_total=lang.format_number(tax_total)))

    @classmethod
    def _check_credit_note_2(cls, root, invoice):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()

        payable_amount = Decimal(
            root.findtext('./{*}LegalMonetaryTotal/{*}PayableAmount'))
        prepaid_amount = Decimal(
            root.findtext('./{*}LegalMonetaryTotal/{*}PrepaidAmount')
            or 0)
        amount = payable_amount + prepaid_amount
        if not getattr(invoice, 'cash_rounding', False):
            payable_rounding_amount = Decimal(
                root.findtext(
                    './{*}LegalMonetaryTotal/{*}PayableRoundingAmount')
                or 0)
            amount -= payable_rounding_amount
        if -invoice.total_amount != amount:
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_invoice_total_amount_different',
                    invoice=invoice.rec_name,
                    total_amount=lang.format_number(-invoice.total_amount),
                    amount=lang.format_number(amount)))

        tax_total = sum(Decimal(amount.text) for amount in root.iterfind(
                './{*}TaxTotal/{*}TaxAmount'))
        if -invoice.tax_amount != tax_total:
            raise InvoiceError(gettext(
                    'edocument_ubl.msg_invoice_tax_amount_different',
                    invoice=invoice.rec_name,
                    tax_amount=lang.format_number(-invoice.tax_amount),
                    tax_total=lang.format_number(tax_total)))


class Invoice_Purchase(metaclass=PoolMeta):
    __name__ = 'edocument.ubl.invoice'

    @classmethod
    def _parse_2_item(cls, item, supplier=None):
        pool = Pool()
        Product = pool.get('product.product')

        product = super()._parse_2_item(item, supplier=supplier)

        if (not product
                and supplier
                and (code := item.findtext(
                        './{*}SellersItemIdentification/{*}ID'))):
            try:
                product, = Product.search([
                        ('product_suppliers', 'where', [
                                ('party', '=', supplier.id),
                                ('code', '=', code),
                                ]),
                        ], limit=1)
            except ValueError:
                pass
        return product

    @classmethod
    def _parse_2_line_reference(
            cls, line_reference, line, company, supplier=None):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        UoM = pool.get('product.uom')

        origin = super()._parse_2_line_reference(
            line_reference, line, company, supplier=supplier)
        if origin:
            return origin
        if not line or not line.product or not line.unit:
            return

        if numbers := list(filter(None, [
                        line_reference.findtext('./{*}OrderReference/{*}ID'),
                        line_reference.findtext(
                            './{*}OrderReference/{*}SalesOrderID'),
                        ])):
            purchase_lines = PurchaseLine.search([
                    ('purchase.company', '=', company),
                    ('purchase.rec_name', 'in', numbers),
                    ('type', '=', 'line'),
                    ('product', '=', line.product),
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
                origin = quantities[index][1]
        return origin
