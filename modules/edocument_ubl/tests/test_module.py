# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import os
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

from lxml import etree

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


def get_invoice():
    pool = Pool()
    Address = pool.get('party.address')
    Company = pool.get('company.company')
    Country = pool.get('country.country')
    Currency = pool.get('currency.currency')
    Identifier = pool.get('party.identifier')
    Invoice = pool.get('account.invoice')
    InvoiceLine = pool.get('account.invoice.line')
    InvoiceTax = pool.get('account.invoice.tax')
    MoveLine = pool.get('account.move.line')
    Party = pool.get('party.party')
    PaymentTerm = pool.get('account.invoice.payment_term')
    Product = pool.get('product.product')
    Tax = pool.get('account.tax')
    Uom = pool.get('product.uom')

    address = Mock(spec=Address,
        street_unstructured="St sample, 15",
        city="Scranton",
        postal_code="1000",
        subdivision=None,
        country=Mock(spec=Country,
            code='US'),
        )
    address.building_name = "Building A"
    address.country.name = "United States"
    identifier = MagicMock(
        spec=Identifier,
        type='be_vat',
        code='BE123456789')
    type(identifier).iso_6523 = Identifier.iso_6523
    type(identifier).eas = Identifier.eas
    type(identifier).unece_code = Identifier.unece_code
    party = MagicMock(
        spec=Party,
        addresses=[address],
        identifiers=[identifier],
        )
    type(party).identifier_iso6523 = Party.identifier_iso6523
    type(party).identifier_eas = Party.identifier_eas
    party.name = "Michael Scott"
    company = Mock(spec=Company,
        party=Mock(
            spec=Party,
            addresses=[Mock(spec=Address,
                    street_unstructured="Main street, 42",
                    country=Mock(spec=Country,
                        code='US'))],
            identifiers=[Mock(
                    spec=Identifier,
                    type='us_ein',
                    code='911144442')],
            ))
    company.party.name = "Dunder Mifflin"
    company.party.address_get = Mock(return_value=company.party.addresses[0])
    taxes = [Mock(spec=InvoiceTax,
            tax=Mock(spec=Tax,
                legal_notice="Legal Notice",
                unece_category_code='S',
                unece_code='VAT',
                type='percentage',
                rate=Decimal('.1'),
                ),
            base=Decimal('100.00'),
            amount=Decimal('10.00'),
            legal_notice="Legal Notice",
            )]
    product = Mock(spec=Product,
        code="12345",
        type='service',
        )
    product.name = "Product"
    product.identifier_get.return_value = '98412345678908'
    lines = [Mock(spec=InvoiceLine,
            type='line',
            product=product,
            unit=Mock(spec=Uom,
                ),
            quantity=1,
            unit_price=Decimal('100.0000'),
            amount=Decimal('100.00'),
            description="Description",
            taxes=[t.tax for t in taxes],
            )]
    invoice = MagicMock(spec=Invoice,
        id=-1,
        __int__=Mock(return_value=-1),
        type='out',
        sequence_type='invoice',
        number="001",
        party=party,
        party_lang='fr',
        party_tax_identifier=identifier,
        invoice_address=party.addresses[0],
        company=company,
        currency=Mock(spec=Currency,
            code='USD',
            round=lambda a: a),
        invoice_date=datetime.date.today(),
        reference="PO1234",
        payment_term=Mock(spec=PaymentTerm, description="Direct"),
        lines=lines,
        line_lines=lines,
        taxes=taxes,
        untaxed_amount=Decimal('100.00'),
        tax_amount=Decimal('10.00'),
        total_amount=Decimal('110.00'),
        amount_to_pay=Decimal('110.00'),
        lines_to_pay=[Mock(spec=MoveLine,
                maturity_date=datetime.date.today(),
                amount=Decimal('110.00'),
                )],
        sales=[],
        state='posted',
        )
    return invoice


class EdocumentUblTestCase(ModuleTestCase):
    "Test Edocument Ubl module"
    module = 'edocument_ubl'
    extras = ['account_invoice', 'document_incoming_invoice', 'purchase']

    @with_transaction()
    def test_Invoice_2(self):
        "Test Invoice-2"
        pool = Pool()
        Template = pool.get('edocument.ubl.invoice')
        InvoiceReport = pool.get('account.invoice', type='report')
        with patch.object(InvoiceReport, 'execute') as execute:
            execute.return_value = ['pdf', b'data', False, 'Invoice-1234']
            invoice = get_invoice()
            template = Template(invoice)

            invoice_string = template.render('2')
            invoice_xml = etree.fromstring(invoice_string)
            schema_file = os.path.join(
                os.path.dirname(__file__),
                '2.4', 'maindoc', 'UBL-Invoice-2.4.xsd')
            schema = etree.XMLSchema(etree.parse(schema_file))
            schema.assertValid(invoice_xml)

    @with_transaction()
    def test_Invoice_2_Peppol_BIS_3(self):
        "Test Invoice-2"
        pool = Pool()
        Template = pool.get('edocument.ubl.invoice')
        InvoiceReport = pool.get('account.invoice', type='report')
        with patch.object(InvoiceReport, 'execute') as execute:
            execute.return_value = ['pdf', b'data', False, 'Invoice-1234']
            invoice = get_invoice()
            template = Template(invoice)

            invoice_string = template.render('2', specification='peppol-bis-3')
            invoice_xml = etree.fromstring(invoice_string)
            schema_file = os.path.join(
                os.path.dirname(__file__),
                '2.4', 'maindoc', 'UBL-Invoice-2.4.xsd')
            schema = etree.XMLSchema(etree.parse(schema_file))
            schema.assertValid(invoice_xml)

    @with_transaction()
    def test_CreditNote_2(self):
        "Test CreditNote-2"
        pool = Pool()
        Template = pool.get('edocument.ubl.invoice')
        InvoiceReport = pool.get('account.invoice', type='report')
        with patch.object(InvoiceReport, 'execute') as execute:
            execute.return_value = ['pdf', b'data', False, 'Invoice-1234']
            invoice = get_invoice()
            invoice.sequence_type = 'credit_note'
            for line in invoice.lines:
                line.quantity *= -1
            invoice.untaxed_amount *= -1
            invoice.tax_amount *= -1
            invoice.total_amount *= -1
            invoice.amount_to_pay *= -1
            for line in invoice.lines_to_pay:
                line.amount *= -1
            template = Template(invoice)

            invoice_string = template.render('2')
            invoice_xml = etree.fromstring(invoice_string)
            schema_file = os.path.join(
                os.path.dirname(__file__),
                '2.4', 'maindoc', 'UBL-CreditNote-2.4.xsd')
            schema = etree.XMLSchema(etree.parse(schema_file))
            schema.assertValid(invoice_xml)

    @with_transaction()
    def test_CreditNote_2_Peppol_BIS_3(self):
        "Test CreditNote-2"
        pool = Pool()
        Template = pool.get('edocument.ubl.invoice')
        InvoiceReport = pool.get('account.invoice', type='report')
        with patch.object(InvoiceReport, 'execute') as execute:
            execute.return_value = ['pdf', b'data', False, 'Invoice-1234']
            invoice = get_invoice()
            invoice.sequence_type = 'credit_note'
            for line in invoice.lines:
                line.quantity *= -1
            invoice.untaxed_amount *= -1
            invoice.tax_amount *= -1
            invoice.total_amount *= -1
            invoice.amount_to_pay *= -1
            for line in invoice.lines_to_pay:
                line.amount *= -1
            template = Template(invoice)

            invoice_string = template.render('2', specification='peppol-bis-3')
            invoice_xml = etree.fromstring(invoice_string)
            schema_file = os.path.join(
                os.path.dirname(__file__),
                '2.4', 'maindoc', 'UBL-CreditNote-2.4.xsd')
            schema = etree.XMLSchema(etree.parse(schema_file))
            schema.assertValid(invoice_xml)


del ModuleTestCase
