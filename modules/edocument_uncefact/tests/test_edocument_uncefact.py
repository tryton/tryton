# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
import os
import unittest
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from lxml import etree

from trytond.pool import Pool
from trytond.tests.test_tryton import (ModuleTestCase, with_transaction,
    activate_module)
from trytond.tests.test_tryton import suite as test_suite


def get_invoice():
    pool = Pool()
    Address = pool.get('party.address')
    Company = pool.get('company.company')
    Country = pool.get('country.country')
    Currency = pool.get('currency.currency')
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
        street="St sample, 15",
        city="Scranton",
        zip="1000",
        subdivision=None,
        country=Mock(spec=Country,
            code='US'),
        )
    address.name = "Building A"
    address.country.name = "United States"
    party = Mock(spec=Party, addresses=[address])
    party.name = "Michael Scott"
    company = Mock(spec=Company,
        party=Mock(spec=Party,
        addresses=[Mock(spec=Address,
                    street="Main street, 42",
                    country=Mock(spec=Country,
                        code='US'))]))
    company.party.name = "Dunder Mifflin"
    company.party.address_get = Mock(return_value=company.party.addresses[0])
    taxes = [Mock(spec=InvoiceTax,
            tax=Mock(spec=Tax,
                unece_code='VAT',
                unece_category_code='S',
                legal_notice="Legal Notice",
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
    lines = [Mock(spec=InvoiceLine,
            type='line',
            product=product,
            unit=Mock(spec=Uom,
                unece_code='C62',
                ),
            quantity=1,
            unit_price=Decimal('100.0000'),
            amount=Decimal('100.00'),
            description="Description",
            invoice_taxes=taxes,
            )]
    invoice = MagicMock(spec=Invoice,
        id=-1,
        __int__=Mock(return_value=-1),
        type='out',
        number="001",
        party=party,
        party_lang='fr',
        invoice_address=party.addresses[0],
        company=company,
        currency=Mock(spec=Currency,
            code='USD',
            round=lambda a: a),
        invoice_date=datetime.date.today(),
        payment_term=Mock(spec=PaymentTerm, description="Direct"),
        lines=lines,
        taxes=taxes,
        untaxed_amount=Decimal('100.00'),
        tax_amount=Decimal('10.00'),
        total_amount=Decimal('110.00'),
        amount_to_pay=Decimal('110.00'),
        lines_to_pay=[Mock(spec=MoveLine,
                maturity_date=datetime.date.today(),
                amount_second_currency=None,
                debit=Decimal('110.00'),
                credit=0,
                )],
        sales=[],
        state='posted',
        )
    return invoice


class EDocumentUNCEFACTTestCase(ModuleTestCase):
    'Test EDocument UN/CEFACT module'
    module = 'edocument_uncefact'

    @classmethod
    def setUpClass(cls):
        super(EDocumentUNCEFACTTestCase, cls).setUpClass()
        activate_module('account_invoice')

    @with_transaction()
    def test_16B_CII_CrossIndustryInvoice(self):
        "Test 16B-CII CrossIndustryInvoice"
        pool = Pool()
        Template = pool.get('edocument.uncefact.invoice')
        invoice = get_invoice()
        template = Template(invoice)

        invoice_string = template.render('16B-CII')
        invoice_xml = etree.fromstring(invoice_string)
        schema_file = os.path.join(
            os.path.dirname(__file__),
            '16B-CII', 'data', 'standard', 'CrossIndustryInvoice_100pD16B.xsd')
        schema = etree.XMLSchema(etree.parse(schema_file))
        schema.assertValid(invoice_xml)


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            EDocumentUNCEFACTTestCase))
    return suite
