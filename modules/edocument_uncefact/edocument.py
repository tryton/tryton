# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import bisect
import datetime as dt
import functools
import os
from decimal import Decimal
from io import BytesIO
from itertools import chain
from operator import itemgetter

import genshi
import genshi.template
# XXX fix: https://genshi.edgewall.org/ticket/582
from genshi.template.astutil import ASTCodeGenerator, ASTTransformer
from lxml import etree
from stdnum import bic, iban

from trytond.i18n import gettext, ngettext
from trytond.model import Model
from trytond.modules.product import round_price
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.tools import cached_property, slugify
from trytond.transaction import Transaction

from .exceptions import InvoiceError

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


def has_goods_assets(func):
    @functools.wraps(func)
    def wrapper(self):
        if any(l.product.type in {'goods', 'assets'}
                for l in self.invoice.lines if l.product):
            return func(self)
    return wrapper


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


DATETIME_FORMATS = {
    '102': '%Y%m%d',
    '203': '%Y%m%d%H%M',
    '204': '%Y%m%d%H%M%S',
    '610': '%Y%m',
    }


class Invoice(Model):
    __name__ = 'edocument.uncefact.invoice'
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

    def render(self, template, exchange_context=None):
        if self.invoice.state not in {'posted', 'paid'}:
            raise ValueError("Invoice must be posted")
        tmpl = self._get_template(template)
        if not tmpl:
            raise NotImplementedError
        return (tmpl.generate(
                this=self,
                exchange_context=exchange_context,
                Decimal=Decimal)
            .filter(remove_comment)
            .render()
            .encode('utf-8'))

    def _get_template(self, version):
        return loader.load(os.path.join(version, 'CrossIndustryInvoice.xml'))

    @property
    def filename(self):
        return f'{slugify(self.invoice.rec_name)}.xml'

    @cached_property
    def type_code(self):
        if self.invoice.type == 'out':
            if all(l.amount < 0 for l in self.lines):
                return '381'
            else:
                return '380'
        else:
            if all(l.amount < 0 for l in self.lines):
                return '261'
            else:
                return '389'

    @cached_property
    def type_sign(self):
        "The sign of the quantity depending of the type code"
        if self.type_code in {'381', '261'}:
            return -1
        return 1

    @cached_property
    def lines(self):
        return [l for l in self.invoice.lines if l.type == 'line']

    @cached_property
    def seller_trade_party(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party
        else:
            return self.invoice.party

    @cached_property
    def seller_trade_address(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party.address_get('invoice')
        else:
            return self.invoice.invoice_address

    @cached_property
    def seller_trade_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.tax_identifier
        else:
            return self.invoice.party_tax_identifier

    @cached_property
    def buyer_trade_party(self):
        if self.invoice.type == 'out':
            return self.invoice.party
        else:
            return self.invoice.company.party

    @cached_property
    def buyer_trade_address(self):
        if self.invoice.type == 'out':
            return self.invoice.invoice_address
        else:
            return None

    @cached_property
    def buyer_trade_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.party_tax_identifier
        else:
            return self.invoice.tax_identifier

    @cached_property
    @has_goods_assets
    def ship_to_trade_party(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales', None):
                sale = self.invoice.sales[0]  # XXX
                if sale.shipment_party != self.buyer_trade_party:
                    return sale.shipment_party
        else:
            if getattr(self.invoice, 'purchases', None):
                purchase = self.invoice.purchases[0]  # XXX
                address = purchase.warehouse.address
                if (address and address.party != self.buyer_trade_party):
                    return address.party

    @cached_property
    @has_goods_assets
    def ship_to_trade_address(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales', None):
                sale = self.invoice.sales[0]  # XXX
                if sale.shipment_party != self.buyer_trade_party:
                    return sale.shipment_address
        else:
            if getattr(self.invoice, 'purchases', None):
                purchase = self.invoice.purchases[0]  # XXX
                address = purchase.warehouse.address
                if (address and address.party != self.buyer_trade_party):
                    return address

    @cached_property
    @has_goods_assets
    def ship_from_trade_party(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales', None):
                sale = self.invoice.sales[0]  # XXX
                address = sale.warehouse.address
                if address and address.party != self.seller_trade_party:
                    return address.shipment_party

    @cached_property
    @has_goods_assets
    def ship_from_trade_address(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales', None):
                sale = self.invoice.sales[0]  # XXX
                address = sale.warehouse.address
                if address and address.party != self.seller_trade_party:
                    return address

    @cached_property
    def payment_reference(self):
        return self.invoice.number

    @classmethod
    def party_legal_ids(cls, party, address):
        return []

    @classmethod
    def parse(cls, document):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        tree = etree.parse(BytesIO(document))
        root = tree.getroot()
        namespace = root.nsmap.get(root.prefix)
        invoice, attachments = cls.parser(namespace)(root)
        invoice.save()
        invoice.update_taxes()
        attachments = list(attachments)
        for attachment in attachments:
            attachment.resource = invoice
        Attachment.save(attachments)
        return invoice

    @classmethod
    def parser(cls, namespace):
        return {
            'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100': (
                cls._parse_cii),
            }.get(namespace)

    @classmethod
    def _parse_cii(cls, root):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Currency = pool.get('currency.currency')

        exchanged_document = root.find('./{*}ExchangedDocument')
        settlement = root.find(
            './{*}SupplyChainTradeTransaction/'
            '{*}ApplicableHeaderTradeSettlement')
        agreement = root.find(
            './{*}SupplyChainTradeTransaction/'
            '{*}ApplicableHeaderTradeAgreement')
        transaction = root.find('./{*}SupplyChainTradeTransaction')

        type_code = exchanged_document.findtext('./{*}TypeCode')
        if type_code and type_code not in {'380', '381'}:
            raise InvoiceError(gettext(
                    'edocument_uncefact.msg_invoice_type_code_unsupported',
                    type_code=type_code))
        type_sign = -1 if type_code == '381' else 1

        invoice = Invoice(type='in')

        if (buyer_trade_party := agreement.find('./{*}BuyerTradeParty')
                ) is not None:
            invoice.company = cls._parse_cii_company(buyer_trade_party)
        else:
            invoice.company = Invoice.default_company()
        if not invoice.company:
            raise InvoiceError(gettext(
                    'edocument_uncefact.msg_company_not_found',
                    company=etree.tostring(
                        buyer_trade_party, pretty_print=True).decode()
                    if buyer_trade_party else ''))

        invoice.reference = exchanged_document.findtext('./{*}ID')
        for invoice_date in chain(
                settlement.iterfind('./{*}InvoiceDateTime/{*}DateTimeString'),
                exchanged_document.iterfind(
                    './{*}IssueDateTime/{*}DateTimeString'),
                ):
            invoice.invoice_date = dt.datetime.strptime(
                invoice_date.text,
                DATETIME_FORMATS.get(invoice_date.get('format') or '102')
                ).date()
        invoice.party = cls._parse_cii_party(
            agreement.find('./{*}SellerTradeParty'), create=True).id
        payees = [invoice.party]
        invoice.set_journal()
        invoice.on_change_party()
        invoice.invoice_address = cls._parse_cii_address(
            agreement.find('./{*}SellerTradeParty/{*}PostalTradeAddress'),
            party=invoice.party)
        invoice.party_tax_identifier = cls._parse_cii_tax_identifier(
            agreement.findall(
                './{*}SellerTradeParty/{*}SpecifiedTaxRegistration'),
            party=invoice.party, create=True)

        if (payee_trade_party := settlement.find('./{*}PayeeTradeParty')
                ) is not None:
            party = cls._parse_cii_party(payee_trade_party, create=True)
            invoice.alternative_payees = [party]
            payees.append(party)
        if (currency_code := settlement.findtext('./{*}InvoiceCurrencyCode')
                ) is not None:
            try:
                invoice.currency, = Currency.search([
                        ('code', '=', currency_code),
                        ], limit=1)
            except ValueError:
                raise InvoiceError(gettext(
                        'edocument_uncefact.msg_currency_not_found',
                        code=currency_code))

        invoice.supplier_payment_reference = settlement.findtext(
            './{*}SpecifiedTradeSettlementPaymentMeans/{*}ID')
        invoice.payment_means = cls._parse_cii_payment_means(
            settlement.findall('./{*}SpecifiedTradeSettlementPaymentMeans'),
            payees=payees)
        invoice.payment_term_date = cls._parse_cii_payment_term_date(
            settlement.findall('./{*}SpecifiedTradePaymentTerms'))
        lines = [
            cls._parse_cii_line(
                line,
                sign=type_sign,
                company=invoice.company,
                currency=invoice.currency,
                supplier=invoice.party)
            for line in transaction.iterfind(
                            './{*}IncludedSupplyChainTradeLineItem')]
        invoice.lines = lines
        invoice.taxes = [
            cls._parse_cii_tax(tax, type_sign, company=invoice.company)
            for tax in settlement.iterfind('./{*}ApplicableTradeTax')]

        if (hasattr(Invoice, 'cash_rounding')
                and (settlement.find(
                        './{*}SpecifiedTradeSettlementHeaderMonetarySummation'
                        '/{*}RoundingAmount') is not None)):
            invoice.cash_rounding = True

        if tax_basis_total_amount := settlement.findtext(
                './{*}SpecifiedTradeSettlementHeaderMonetarySummation'
                '/{*}TaxBasisTotalAmount'):
            untaxed_amount = Decimal(tax_basis_total_amount)
            # TODO: Allowance
            invoice.source_untaxed_amount = untaxed_amount * type_sign

        if tax_total_amount := settlement.findtext(
                './{*}SpecifiedTradeSettlementHeaderMonetarySummation'
                '/{*}TaxTotalAmount'):
            invoice.source_tax_amount = Decimal(tax_total_amount) * type_sign
        if grand_total_amount := settlement.findtext(
                './{*}SpecifiedTradeSettlementHeaderMonetarySummation'
                '/{*}GrandTotalAmount'):
            invoice.source_total_amount = (
                Decimal(grand_total_amount) * type_sign)

        return invoice, cls._parse_cii_attachments(root)

    @classmethod
    def _parse_cii_line(
            cls, invoice_item, sign, company, currency, supplier=None):
        pool = Pool()
        Line = pool.get('account.invoice.line')
        UoM = pool.get('product.uom')
        Tax = pool.get('account.tax')
        AccountConfiguration = pool.get('account.configuration')

        account_configuration = AccountConfiguration(1)

        line = Line(
            type='line', company=company, currency=currency, invoice_type='in')
        if (billed_quantity := invoice_item.find(
                    './{*}SpecifiedLineTradeDelivery/{*}BilledQuantity')
                ) is not None:
            line.quantity = float(billed_quantity.text)
            digits = (
                -Decimal(billed_quantity.text)
                .normalize().as_tuple().exponent)
            if (unit_code := billed_quantity.get('unitCode')) not in {
                    None, 'ZZ', 'XZZ'}:
                try:
                    line.unit, = UoM.search([
                            ('unece_code', '=', unit_code),
                            ('digits', '>=', digits),
                            ],
                        order=[('digits', 'ASC')],
                        limit=1)
                except ValueError:
                    raise InvoiceError(ngettext(
                            'edocument_uncefact.msg_unit_not_found',
                            digits,
                            code=unit_code,
                            digits=digits))
            else:
                line.unit = None
        else:
            line.quantity = 1
            line.unit = None
            digits = 0

        line.product = cls._parse_cii_product(
            invoice_item.find('./{*}SpecifiedTradeProduct'), supplier=supplier)
        if line.product:
            line.on_change_product()
            if line.unit and line.unit.digits < digits:
                # Search the unit with enough digits
                try:
                    line.unit, = UoM.search([
                            ('category', '=', line.unit.category),
                            ('digits', '>=', digits),
                            ['OR',
                                ('factor', '=', line.unit.factor),
                                ('rate', '=', line.unit.rate),
                                ],
                            ],
                        order=[('digits', 'ASC')],
                        limit=1)
                except ValueError:
                    pass
        line.description = "\n".join(e.text for e in chain(
                invoice_item.iterfind('./{*}SpecifiedTradeProduct/{*}Name'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}TradeName'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}Description'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}EndItemName'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}UseDescription'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}BrandName'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}SubBrandName'),
                invoice_item.iterfind(
                    './{*}SpecifiedTradeProduct/{*}Designation'),
                ) if e is not None and e.text)

        if not line.product:
            if line.description:
                similar_domain = [
                    ('description', 'ilike', line.description),
                    ('invoice.company', '=', company),
                    ('invoice.type', '=', 'in'),
                    ('invoice.state', 'in',
                        ['validated', 'posted', 'paid']),
                    ]
                if line.unit:
                    similar_domain.append(
                        ('unit.category', '=', line.unit.category))
                similar_lines = Line.search(
                    similar_domain,
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

        line_trade_agreement = invoice_item.find(
            './{*}SpecifiedLineTradeAgreement')
        for reference in chain(
                line_trade_agreement.iterfind(
                    './{*}SellerOrderReferencedDocument'),
                line_trade_agreement.iterfind(
                    './{*}BuyerOrderReferencedDocument'),
                line_trade_agreement.iterfind(
                    './{*}QuotationReferencedDocument'),
                line_trade_agreement.iterfind(
                    './{*}ContractReferencedDocument'),
                line_trade_agreement.iterfind(
                    './{*}DemandForecastReferencedDocument'),
                line_trade_agreement.iterfind(
                    './{*}PromotionalDealReferencedDocument'),
                line_trade_agreement.iterfind(
                    './{*}AdditionalReferencedDocument'),
                ):
            line.origin = cls._parse_cii_line_reference(
                reference, line, company, supplier=supplier)
            if line.origin:
                break

        unit_price = Decimal(line_trade_agreement.findtext(
                './{*}NetPriceProductTradePrice/{*}ChargeAmount'))
        if (basis_quantity := line_trade_agreement.find(
                './{*}NetPriceProductTradePrice/{*}BasisQuantity')
                ) is not None:
            unit_price /= Decimal(basis_quantity.text)
        line.unit_price = round_price(abs(unit_price))

        line_trade_settlement = invoice_item.find(
            './{*}SpecifiedLineTradeSettlement')

        total_amount = Decimal(line_trade_settlement.findtext(
                './{*}SpecifiedTradeSettlementLineMonetarySummation'
                '/{*}LineTotalAmount'))
        line.quantity = (
            -abs(line.quantity) if total_amount.is_signed()
            else abs(line.quantity)) * sign

        taxes = []
        for trade_tax in line_trade_settlement.iterfind(
                './{*}ApplicableTradeTax'):
            domain = cls._parse_cii_tax_domain(trade_tax)
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
                        'edocument_uncefact.msg_tax_not_found',
                        tax_category=etree.tostring(
                            trade_tax, pretty_print=True).decode()))
            taxes.append(tax)
        line.taxes = taxes
        return line

    @classmethod
    def _parse_cii_party(cls, trade_party, create=False):
        pool = Pool()
        Party = pool.get('party.party')

        for identifier in chain(
                trade_party.iterfind('./{*}ID'),
                trade_party.iterfind('./{*}GlobalID'),
                trade_party.iterfind('./{*}SpecifiedLegalOrganization/{*}ID'),
                trade_party.iterfind('./{*}SpecifiedTaxRegistration/{*}ID'),
                ):
            if identifier.text:
                domain = [
                    ('code_compact', '=', identifier.text),
                    ]
                if schemeId := identifier.get('schemeID'):
                    if schemeId == 'VA':
                        domain.append(('type', '=', 'eu_vat'))
                parties = Party.search([
                        ('identifiers', 'where', domain),
                        ])
                if len(parties) == 1:
                    party, = parties
                    return party
        if create:
            party = cls._create_cii_party(trade_party)
            party.save()
        return party

    @classmethod
    def _create_cii_party(cls, trade_party):
        pool = Pool()
        Party = pool.get('party.party')
        party = Party()
        party.name = (
            trade_party.findtext('./{*}SpecifiedLegalOrganization/{*}Name')
            or trade_party.findtext(
                './{*}SpecifiedLegalOrganization/{*}TradingBusinessName')
            or trade_party.findtext('./{*}Name'))
        identifiers = []
        identifiers_done = set()
        for identifier in chain(
                trade_party.iterfind('./{*}ID'),
                trade_party.iterfind('./{*}GlobalID'),
                trade_party.iterfind('./{*}SpecifiedLegalOrganization/{*}ID'),
                trade_party.iterfind('./{*}SpecifiedTaxRegistration/{*}ID'),
                ):
            if identifier.text:
                identifier_key = (identifier.text, identifier.get('schemeID'))
                if identifier_key not in identifiers_done:
                    identifiers.append(cls._create_cii_party_identifier(
                            identifier))
                identifiers_done.add(identifier_key)
        party.identifiers = identifiers
        if (address := trade_party.find('./{*}PostalTradeAddress')
                ) is not None:
            party.addresses = [cls._create_cii_address(address)]
        return party

    @classmethod
    def _create_cii_party_identifier(cls, identifier):
        pool = Pool()
        Identifier = pool.get('party.identifier')
        type = None
        if schemeID := identifier.get('schemeID'):
            if schemeID == 'VA':
                type = 'eu_vat'
        return Identifier(type=type, code=identifier.text)

    @classmethod
    def _parse_cii_address(cls, address_el, party):
        pool = Pool()
        Address = pool.get('party.address')

        address = cls._create_cii_address(address_el)

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
    def _create_cii_address(cls, address_el):
        pool = Pool()
        Address = pool.get('party.address')
        Country = pool.get('country.country')
        Subdivision = pool.get('country.subdivision')

        address = Address()

        if address_el is None:
            return address

        address.postal_code = address_el.findtext('./{*}PostcodeCode')
        address.post_box = address_el.findtext('./{*}PostOfficeBox')
        address.building_name = address_el.findtext('./{*}BuildingName')
        address.street_name = address_el.findtext('./{*}StreetName')
        address.city = address_el.findtext('./{*}CityName')
        if country_id := address_el.findtext('./{*}CountryID'):
            try:
                country, = Country.search([
                        ('code', '=', country_id),
                        ], limit=1)
            except ValueError:
                pass
            else:
                address.country = country
                if subdivision_id := address_el.findtext(
                        './{*}CountrySubDivisionID'):
                    try:
                        subdivision, = Subdivision.search([
                                ('code', '=', subdivision_id),
                                ('country', '=', country),
                                ('type', 'in', country.subdivision_types),
                                ], limit=1)
                    except ValueError:
                        pass
                    else:
                        address.subdivision = subdivision
        address.building_number = address_el.findtext('./{*}BuildingNumber')

        address.street_unstructured = '\n'.join(filter(None, (
                    address_el.findtext('./{*}LineOne'),
                    address_el.findtext('./{*}LineTwo'),
                    address_el.findtext('./{*}LineThree'),
                    address_el.findtext('./{*}LineFour'),
                    address_el.findtext('./{*}LineFive'),
                    )))
        return address

    @classmethod
    def _parse_cii_tax_identifier(cls, tax_registrations, party, create=False):
        pool = Pool()
        Identifier = pool.get('party.identifier')

        tax_identifier_types = party.tax_identifier_types()

        for tax_registration in tax_registrations:
            id_ = tax_registration.find('./{*}ID')
            if id_ is not None:
                scheme_id = id_.get('schemeID')
                value = id_.text

                for identifier in party.identifiers:
                    if (identifier.type in tax_identifier_types
                            and identifier.code_compact == value):
                        return identifier
                else:
                    if create and scheme_id == 'VA':
                        identifier = Identifier(
                            party=party,
                            type='eu_vat',
                            code=value)
                        identifier.save()
                        return identifier

    @classmethod
    def _parse_cii_company(cls, trade_party):
        pool = Pool()
        Company = pool.get('company.company')

        for identifier in chain(
                trade_party.iterfind('./{*}ID'),
                trade_party.iterfind('./{*}GlobalID'),
                trade_party.iterfind('./{*}SpecifiedLegalOrganization/{*}ID'),
                trade_party.iterfind('./{*}SpecifiedTaxRegistration/{*}ID'),
                ):
            if identifier.text:
                domain = [
                    ('code_compact', '=', identifier.text),
                    ]
                if schemeId := identifier.get('schemeID'):
                    if schemeId == 'VA':
                        domain.append(('type', '=', 'eu_vat'))
                companies = Company.search([
                        ('party.identifiers', 'where', domain),
                        ])
                if len(companies) == 1:
                    company, = companies
                    return company

        for name in chain(
                trade_party.iterfind(
                    './{*}SpecifiedLegalOrganization/{*}Name'),
                trade_party.iterfind(
                    './{*}SpecifiedLegalOrganization/{*}TradingBusinessName'),
                trade_party.iterfind('./{*}Name'),
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
    def _parse_cii_payment_means(cls, payment_means, payees):
        pool = Pool()
        PaymentMean = pool.get('account.invoice.payment.mean')
        means = []
        for payment_mean in payment_means:
            if instrument := cls._parse_cii_payment_mean(payment_mean, payees):
                means.append(PaymentMean(instrument=instrument))
        return means

    @classmethod
    def _parse_cii_payment_mean(cls, payment_mean, payees):
        pass

    @classmethod
    def _parse_cii_payment_term_date(cls, payment_terms):
        dates = []
        for payment_term in payment_terms:
            if (date := payment_term.find(
                    './{*}DueDateDateTime/DateTimeString') is not None):
                dates.append(dt.datetime.strptime(
                        date.text,
                        DATETIME_FORMATS.get(date.get('format') or '102')
                        ).date())
        return min(dates, default=None)

    @classmethod
    def _parse_cii_product(cls, product_el, supplier=None):
        pool = Pool()
        Product = pool.get('product.product')

        for identifier in chain(
                product_el.iterfind('./{*}ID'),
                product_el.iterfind('./{*}GlobalID'),
                product_el.iterfind('./{*}ManufacturerAssignedID'),
                ):
            if identifier.text:
                domain = [
                    ('code', '=', identifier.text),
                    ]
                # TOOD: schemeID
                try:
                    product, = Product.search([
                            ('identifiers', 'where', domain),
                            ], limit=1)
                except ValueError:
                    pass
                else:
                    return product
        if code := product_el.findtext('./{*}BuyerAssignedID'):
            try:
                product, = Product.search([
                        ('code', '=', code),
                        ], limit=1)
            except ValueError:
                pass
            else:
                return product

    @classmethod
    def _parse_cii_line_reference(
            cls, reference, line, company, supplier=None):
        pass

    @classmethod
    def _parse_cii_tax_domain(cls, tax):
        pool = Pool()
        Tax = pool.get('account.tax')
        domain = [
            ('parent', '=', None),
            ]
        if (unece_category_code := tax.findtext('./{*}CategoryCode')
                ) is not None:
            domain.append(('unece_category_code', '=', unece_category_code))
        if (unece_code := tax.findtext('./{*}TypeCode')) is not None:
            domain.append(('unece_code', '=', unece_code))
        if percent := tax.findtext('./{*}RateApplicablePercent'):
            domain.append(('type', '=', 'percentage'))
            domain.append(('rate', '=', Decimal(percent) / 100))
        if (hasattr(Tax, 'vatex_code')
                and (tax_exemption_reason_code := tax.findtext(
                        './{*}ExemptionReasonCode'))):
            domain.append(['OR',
                    ('vatex_code', '=', tax_exemption_reason_code),
                    ('vatex_code', '=', None),
                    ])
        return domain

    @classmethod
    def _parse_cii_tax(cls, tax, sign, company):
        pool = Pool()
        Tax = pool.get('account.tax')
        InvoiceTax = pool.get('account.invoice.tax')

        invoice_tax = InvoiceTax(manual=False)
        domain = cls._parse_cii_tax_domain(tax)
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
                    'edocument_uncefact.msg_tax_not_found',
                    tax_category=etree.tostring(
                        tax, pretty_print=True).decode()))

        invoice_tax.amount = sign * Decimal(
            tax.findtext('./{*}CalculatedAmount'))
        if (basis_amount := tax.findtext('./{*}BasisAmount')) is not None:
            invoice_tax.base = Decimal(basis_amount)
        else:
            # Use tax amount to define the sign of unknown base
            invoice_tax.base = invoice_tax.amount

        invoice_tax.on_change_tax()

        return invoice_tax

    @classmethod
    def _parse_cii_attachments(cls, root):
        yield from ()


class Invoice_Bank(metaclass=PoolMeta):
    __name__ = 'edocument.uncefact.invoice'

    @classmethod
    def _parse_cii_payment_mean(cls, payment_mean, payees):
        pool = Pool()
        Account = pool.get('bank.account')
        instrument = super()._parse_cii_payment_mean(payment_mean, payees)
        if (financial_account := payment_mean.find(
                    './{*}PayeePartyCreditorFinancialAccount')) is not None:
            if iban := financial_account.findtext('./{*}IBANID'):
                try:
                    account, = Account.search([
                            ('numbers', 'where', ['OR',
                                    ('number', '=', iban),
                                    ('number_compact', '=', iban),
                                    ]),
                            ('owners.id', 'in', payees),
                            ], limit=1)
                except ValueError:
                    party = payees[-1]
                    if party.id in Transaction().create_records['party.party']:
                        account = cls._create_cii_bank_account(
                            financial_account, party)
                        account.save()
                    else:
                        raise InvoiceError(ngettext(
                                'edocument_uncefact.'
                                'msg_bank_account_not_found',
                                len(payees),
                                parties=', '.join(
                                    [p.rec_name for p in payees]),
                                account=etree.tostring(
                                    financial_account,
                                    pretty_print=True).decode()))
                instrument = account
        return instrument

    @classmethod
    def _create_cii_bank_account(cls, financial_account, party):
        pool = Pool()
        Bank = pool.get('bank')
        Account = pool.get('bank.account')
        Number = pool.get('bank.account.number')
        account = Account(owners=[party])
        if identifier := financial_account.findtext('./{*}IBANID'):
            number = Number(number=identifier)
            if iban.is_valid(identifier):
                number.type = 'iban'
            else:
                number.type = 'other'
            account.numbers = [number]
        if identifier := financial_account.findtext(
                './{*}PayeeSpecifiedCreditorFinancialInstitution/{*}BICID'):
            if bic.is_valid(identifier):
                account.bank = Bank.from_bic(identifier)
        return account


class Invoice_Purchase(metaclass=PoolMeta):
    __name__ = 'edocument.uncefact.invoice'

    @classmethod
    def _parse_cii_product(cls, product_el, supplier=None):
        pool = Pool()
        Product = pool.get('product.product')

        product = super()._parse_cii_product(product_el, supplier=supplier)

        if (not product
                and supplier
                and (code := product_el.findtext('./{*}SellerAssignedID'))):
            try:
                product, = Product.search([
                        ('product_suppliers', 'where', [
                                ('party', '=', supplier),
                                ('code', '=', code),
                                ]),
                        ], limit=1)
            except ValueError:
                pass
        return product

    @classmethod
    def _parse_cii_line_reference(
            cls, reference, line, company, supplier=None):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')
        UoM = pool.get('product.uom')

        origin = super()._parse_cii_line_reference(
            reference, line, company, supplier=supplier)
        if origin:
            return origin
        if not line or not line.product or not line.unit:
            return

        if reference.tag not in {
                'SellerOrderReferencedDocument',
                'BuyerOrderReferencedDocument',
                'QuotationReferencedDocument'}:
            return

        if numbers := list(filter(None, [
                        reference.findtext('./{*}IssuerAssignedID'),
                        reference.findtext('./{*}URIID'),
                        reference.findtext('./{*}GlobalID'),
                        reference.findtext('./{*}RevisionID'),
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
