# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal

from trytond.modules.account.tests import create_chart, get_fiscalyear
from trytond.modules.account_invoice.tests import set_invoice_sequences
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.currency.tests import add_currency_rate, create_currency
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

today = datetime.date.today()


def create_party(name, identifier_type, identifier_code):
    pool = Pool()
    Party = pool.get('party.party')
    party, = Party.create([{
                'name': name,
                'addresses': [('create', [{}])],
                'identifiers':
                [('create', [{
                                'type': identifier_type,
                                'code': identifier_code,
                                }])]}])
    return party


def create_invoice(type_, company, party, taxes, currency=None, quantity=1):
    pool = Pool()
    Account = pool.get('account.account')
    Journal = pool.get('account.journal')
    Invoice = pool.get('account.invoice')
    InvoiceSII = pool.get('account.invoice.sii')

    if type_ == 'out':
        kind = 'revenue'
        invoice_account = party.account_receivable_used
    else:
        kind = 'expense'
        invoice_account = party.account_payable_used
    journal, = Journal.search([
            ('type', '=', kind),
            ], limit=1)
    line_account, = Account.search([
            ('type.%s' % kind, '=', True),
            ], limit=1)
    if currency is None:
        currency = company.currency
    invoice, = Invoice.create([{
                'type': type_,
                'company': company.id,
                'currency': currency.id,
                'party': party.id,
                'invoice_address': party.addresses[0].id,
                'journal': journal.id,
                'account': invoice_account.id,
                'invoice_date': today,
                'lines': [
                    ('create', [{
                                'currency': currency.id,
                                'account': line_account.id,
                                'quantity': quantity,
                                'unit_price': Decimal('50'),
                                'taxes': [('add', [t.id for t in taxes])],
                                }]),
                    ],
                }])
    Invoice.post([invoice])
    sii_invoices = InvoiceSII.search([('invoice', '=', invoice.id)])
    if sii_invoices:
        sii_invoice, = sii_invoices
        return sii_invoice
    return sii_invoices


class AccountEsSiiTestCase(ModuleTestCase):
    "Test Account Es Sii module"
    module = 'account_es_sii'

    @with_transaction()
    def test_party_identifier_sii_values(self):
        "Test party identifier sii values"

        for type_, code, value in [
                ('eu_vat', 'ES00000000T', {'NIF': '00000000T'}),
                ('es_nif', '00000000T', {'NIF': '00000000T'}),
                ('eu_vat', 'BE0897290877', {
                        'IDOtro': {
                            'ID': 'BE0897290877',
                            'IDType': '02',
                            'CodigoPais': 'BE',
                            },
                        }),
                ('eu_vat', 'EL094259216', {
                        'IDOtro': {
                            'ID': 'GR094259216',
                            'IDType': '02',
                            'CodigoPais': 'GR',
                            }
                        }),
                ('ad_nrt', 'L709604E', {
                        'IDOtro': {
                            'ID': 'ADL709604E',
                            'IDType': '06',
                            'CodigoPais': 'AD',
                            }
                        }),
                ]:

            party = create_party('Customer', type_, code)
            self.assertDictEqual(party.tax_identifier.es_sii_values(), value)

    @with_transaction()
    def test_fiscalyear_sii_send_invoices(self):
        "Test Fiscalyear SII send invoices"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])

            self.assertFalse(fiscalyear.es_sii_send_invoices)

            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()
            self.assertTrue(fiscalyear.es_sii_send_invoices)

            period = fiscalyear.periods[0]
            period.es_sii_send_invoices = False
            period.save()

            fiscalyear = FiscalYear(fiscalyear.id)
            self.assertIsNone(fiscalyear.es_sii_send_invoices)

    @with_transaction()
    def test_customer_invoice_sii_payload(self):
        "Test Customer Invoice SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()
            fiscalyear.es_sii_send_invoices = True

            party = create_party('Customer', 'eu_vat', 'ES00000000T')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA 21% (bienes)'),
                    ('group.kind', '=', 'sale'),
                    ])
            sii_invoice = create_invoice('out', company, party, [tax])

            payload = sii_invoice.get_payload()

            self.assertListEqual(
                list(payload.keys()),
                ['PeriodoLiquidacion', 'IDFactura', 'FacturaExpedida'])
            self.assertEqual(
                payload['FacturaExpedida']['TipoFactura'], 'F1')
            self.assertEqual(
                payload['FacturaExpedida']['ImporteTotal'], '60.50')
            invoice_detail = {
                'DesgloseFactura': {
                    'Sujeta': [{
                            'NoExenta': {
                                'TipoNoExenta': 'S1',
                                'DesgloseIVA': {
                                    'DetalleIVA': [{
                                            'BaseImponible': Decimal('50.00'),
                                            'TipoImpositivo': '21.00',
                                            'CuotaRepercutida': (
                                                Decimal('10.50')),
                                            }],
                                    },
                                },
                            }]
                    },
                }
            self.assertDictEqual(
                payload['FacturaExpedida']['TipoDesglose'], invoice_detail)

    @with_transaction()
    def test_customer_invoice_excempt_sii_payload(self):
        "Test Customer Invoice Excempt SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Customer', 'es_nif', '00000000T')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA Exento (bienes)'),
                    ('group.kind', '=', 'sale'),
                    ])
            sii_invoice = create_invoice('out', company, party, [tax])

            payload = sii_invoice.get_payload()

            invoice_detail = {
                'DesgloseFactura': {
                    'Sujeta': [{
                            'Exenta': {
                                'DetalleExenta': {
                                    'CausaExencion': 'E1',
                                    'BaseImponible': Decimal('50.00'),
                                    },
                                },
                            }],
                    },
                }
            self.assertDictEqual(
                payload['FacturaExpedida']['TipoDesglose'], invoice_detail)

    @with_transaction()
    def test_customer_surcharge_tax_invoice_sii_payload(self):
        "Test Customer Surcharge Tax Invoice SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Customer', 'eu_vat', 'ES00000000T')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'Recargo Equivalencia 1.4%'),
                    ('group.kind', '=', 'sale'),
                    ])
            sii_invoice = create_invoice(
                'out', company, party, [tax.es_reported_with, tax])

            payload = sii_invoice.get_payload()

            self.assertEqual(
                payload['FacturaExpedida']['ImporteTotal'], '55.70')
            tax_detail = {
                'DetalleIVA': [{
                        'BaseImponible': Decimal('50.00'),
                        'TipoImpositivo': '10.0',
                        'CuotaRepercutida': (
                            Decimal('5.00')),
                        'TipoRecargoEquivalencia': '1.4',
                        'CuotaRecargoEquivalencia': (
                            Decimal('0.70')),
                        },
                    ],
                }
            self.assertDictEqual(
                payload['FacturaExpedida']['TipoDesglose']['DesgloseFactura'][
                    'Sujeta'][0]['NoExenta']['DesgloseIVA'], tax_detail)

    @with_transaction()
    def test_customer_intracomunitary_invoice_sii_payload(self):
        "Test Customer Intracomunitary Invoice Excempt SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Customer', 'eu_vat', 'BE0897290877')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA Intracomunitario (bienes)'),
                    ('group.kind', '=', 'sale'),
                    ])
            sii_invoice = create_invoice('out', company, party, [tax])

            payload = sii_invoice.get_payload()

            invoice_detail = {
                'Entrega': {
                    'Sujeta': [{
                            'Exenta': {
                                'DetalleExenta': {
                                    'CausaExencion': 'E5',
                                    'BaseImponible': Decimal('50.00'),
                                    },
                                },
                            }],
                    },
                }
            self.assertDictEqual(
                payload['FacturaExpedida']['TipoDesglose'][
                    'DesgloseTipoOperacion'], invoice_detail)

    @with_transaction()
    def test_customer_invoice_alternate_currency_sii_payload(self):
        "Test Customer Invoice Alternate Currency SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            currency = create_currency('gbp')
            add_currency_rate(currency, 2)

            party = create_party('Customer', 'eu_vat', 'ES00000000T')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA 21% (bienes)'),
                    ('group.kind', '=', 'sale'),
                    ])
            sii_invoice = create_invoice(
                'out', company, party, [tax], currency=currency)

            payload = sii_invoice.get_payload()

            self.assertEqual(
                payload['FacturaExpedida']['ImporteTotal'], '30.25')
            tax_detail = {
                'DetalleIVA': [{
                        'BaseImponible': Decimal('25.00'),
                        'TipoImpositivo': '21.00',
                        'CuotaRepercutida': (
                            Decimal('5.25')),
                        },
                    ],
                }
            self.assertDictEqual(
                payload['FacturaExpedida']['TipoDesglose']['DesgloseFactura'][
                    'Sujeta'][0]['NoExenta']['DesgloseIVA'], tax_detail)

    @with_transaction()
    def test_customer_credit_note_sii_payload(self):
        "Test Customer Credit Note SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Customer', 'eu_vat', 'ES00000000T')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA 21% (bienes)'),
                    ('group.kind', '=', 'sale'),
                    ])
            sii_invoice = create_invoice(
                'out', company, party, [tax], quantity=-1)

            payload = sii_invoice.get_payload()

            self.assertEqual(
                payload['FacturaExpedida']['ImporteTotal'], '-60.50')
            self.assertEqual(
                payload['FacturaExpedida']['TipoFactura'], 'R1')
            self.assertEqual(
                payload['FacturaExpedida']['TipoRectificativa'], 'I')
            tax_detail = {
                'DetalleIVA': [{
                        'BaseImponible': Decimal('-50.00'),
                        'TipoImpositivo': '21.00',
                        'CuotaRepercutida': (
                            Decimal('-10.50')),
                        },
                    ],
                }
            self.assertDictEqual(
                payload['FacturaExpedida']['TipoDesglose']['DesgloseFactura'][
                    'Sujeta'][0]['NoExenta']['DesgloseIVA'], tax_detail)

    @with_transaction()
    def test_supplier_invoice_sii_payload(self):
        "Test Supplier Invoice SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Supplier', 'eu_vat', 'ES00000000T')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA 10% (bienes)'),
                    ('group.kind', '=', 'purchase'),
                    ])
            sii_invoice = create_invoice('in', company, party, [tax])

            payload = sii_invoice.get_payload()

            self.assertListEqual(
                list(payload.keys()),
                ['PeriodoLiquidacion', 'IDFactura', 'FacturaRecibida'])
            self.assertEqual(
                payload['FacturaRecibida']['TipoFactura'], 'F1')
            self.assertEqual(
                payload['FacturaRecibida'][
                    'ClaveRegimenEspecialOTrascendencia'], '01')
            self.assertEqual(
                payload['FacturaRecibida']['ImporteTotal'], '55.00')
            self.assertEqual(
                payload['FacturaRecibida']['CuotaDeducible'], '5.00')

            invoice_detail = {
                'DesgloseIVA': {
                    'DetalleIVA': [{
                            'BaseImponible': Decimal('50.00'),
                            'TipoImpositivo': '10.0',
                            'CuotaSoportada': Decimal('5.00')}]}}
            self.assertDictEqual(
                payload['FacturaRecibida']['DesgloseFactura'], invoice_detail)

    @with_transaction()
    def test_supplier_intracomunitary_invoice_sii_payload(self):
        "Test Supplier Intracomunitary Invoice SII Payload"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Supplier', 'eu_vat', 'BE0897290877')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA Intracomunitario 21% (bienes)'),
                    ('group.kind', '=', 'purchase'),
                    ])
            sii_invoice = create_invoice('in', company, party, [tax])

            payload = sii_invoice.get_payload()

            self.assertListEqual(
                list(payload.keys()),
                ['PeriodoLiquidacion', 'IDFactura', 'FacturaRecibida'])
            self.assertEqual(
                payload['FacturaRecibida']['TipoFactura'], 'F1')
            self.assertEqual(
                payload['FacturaRecibida'][
                    'ClaveRegimenEspecialOTrascendencia'], '09')
            self.assertEqual(
                payload['FacturaRecibida']['ImporteTotal'], '60.50')
            self.assertEqual(
                payload['FacturaRecibida']['CuotaDeducible'], '10.50')

            invoice_detail = {
                'DesgloseIVA': {
                    'DetalleIVA': [{
                            'BaseImponible': Decimal('50.00'),
                            'TipoImpositivo': '21.00',
                            'CuotaSoportada': Decimal('10.50')}]}}
            self.assertDictEqual(
                payload['FacturaRecibida']['DesgloseFactura'], invoice_detail)

    @with_transaction()
    def test_taxes_excluded_from_sii_taxes(self):
        "Test Taxes excluded from SII"
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Tax = pool.get('account.tax')
        company = create_company()
        with set_company(company):
            create_chart(company, chart='account_es.pgc_0_pyme')
            fiscalyear = set_invoice_sequences(get_fiscalyear(company))
            fiscalyear.save()
            FiscalYear.create_period([fiscalyear])
            fiscalyear.es_sii_send_invoices = True
            fiscalyear.save()

            party = create_party('Supplier', 'eu_vat', 'BE0897290877')
            tax, = Tax.search([
                    ('company', '=', company.id),
                    ('name', '=', 'IVA Importaciones (bienes)'),
                    ('group.kind', '=', 'purchase'),
                    ])
            self.assertTrue(tax.es_exclude_from_sii)

            sii_invoice = create_invoice('in', company, party, [tax])

            self.assertEqual(sii_invoice, [])


del ModuleTestCase
