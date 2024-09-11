===========================================
Account ES Reporting Surcharge Tax Scenario
===========================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from functools import partial

    >>> from proteus import Model, Report
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     'account_es',
    ...     create_company, partial(create_chart, chart='account_es.pgc_0_pyme'))

Setup company::

    >>> company = get_company()
    >>> tax_identifier = company.party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ESB01000009'
    >>> company.party.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(
    ...         company, (dt.date(2020, 1, 1), dt.date(2020, 12, 31))))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> tax_identifier = party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES00000000T'
    >>> party.save()
    >>> surcharge_party = Party(name='Surcharge Party')
    >>> tax_identifier = surcharge_party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES00000001R'
    >>> surcharge_party.save()

Create invoices::

    >>> Tax = Model.get('account.tax')
    >>> tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21% (bienes)'),
    ...     ])
    >>> surcharge_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'sale'),
    ...     ('es_reported_with', '=', tax.id),
    ...     ])
    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = fiscalyear.start_date
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.taxes.append(tax)
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('121.00')
    >>> invoice = Invoice()
    >>> invoice.party = surcharge_party
    >>> invoice.invoice_date = fiscalyear.start_date
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.taxes.append(Tax(tax.id))
    >>> line.taxes.append(surcharge_tax)
    >>> line.quantity = 2
    >>> line.unit_price = Decimal('25')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('63.10')
    >>> invoice, = invoice.duplicate()
    >>> invoice.invoice_date = fiscalyear.start_date
    >>> line, = invoice.lines
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('0.03')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('0.04')

Generate VAT Book::

    >>> VatBook = Model.get('account.reporting.vat_book_es')
    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'es_vat_book_type': 'E',
    ...     }
    >>> with config.set_context(context):
    ...     records = VatBook.find([])
    ...     report = Report('account.reporting.aeat.vat_book')
    ...     extension, content, _, name = report.execute(records)
    >>> len(records)
    3
    >>> tax_record = [r for r in records if not r.surcharge_tax][0]
    >>> assertEqual(tax_record.party, party)
    >>> tax_record.base_amount
    Decimal('100.00')
    >>> tax_record.tax_amount
    Decimal('21.00')
    >>> surcharge_tax_record = [r for r in records if r.surcharge_tax][0]
    >>> assertEqual(surcharge_tax_record.party, surcharge_party)
    >>> surcharge_tax_record.base_amount
    Decimal('50.00')
    >>> surcharge_tax_record.tax_amount
    Decimal('10.50')
    >>> surcharge_tax_record.surcharge_tax_amount
    Decimal('2.60')
    >>> with file_open('account_es/tests/vat_book.csv', 'rb') as f:
    ...     assertEqual(content, f.read())
    >>> name
    'VAT Book-...'
    >>> extension
    'csv'
