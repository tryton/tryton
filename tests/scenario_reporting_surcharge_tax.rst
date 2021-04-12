===========================================
Account ES Reporting Surcharge Tax Scenario
===========================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts, create_fiscalyear)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_es')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> tax_identifier = company.party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ESB01000009'
    >>> company.party.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, datetime.date(2020, 1, 1)))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company, 'account_es.pgc_0_pyme')
    >>> accounts = get_accounts(company)
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
    2
    >>> tax_record, = [r for r in records if not r.surcharge_tax]
    >>> tax_record.party == party
    True
    >>> tax_record.base_amount == Decimal('100.00')
    True
    >>> tax_record.tax_amount == Decimal('21.00')
    True
    >>> surcharge_tax_record, = [r for r in records if r.surcharge_tax]
    >>> surcharge_tax_record.party == surcharge_party
    True
    >>> surcharge_tax_record.base_amount == Decimal('50.00')
    True
    >>> surcharge_tax_record.tax_amount == Decimal('10.50')
    True
    >>> surcharge_tax_record.surcharge_tax_amount == Decimal('2.60')
    True
    >>> with file_open('account_es/tests/vat_book.csv', 'rb') as f:
    ...     content == f.read()
    True
    >>> name.startswith('VAT Book')
    True
    >>> extension
    'csv'
