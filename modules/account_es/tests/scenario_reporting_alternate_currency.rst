================================================
Account ES Reporting Alternate Currency Scenario
================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from functools import partial

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     'account_es',
    ...     create_company, partial(create_chart, chart='account_es.pgc_0_pyme'))

Get company::

    >>> currency = get_currency('USD')
    >>> eur = get_currency('EUR')
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> TaxRule = Model.get('account.tax.rule')
    >>> party = Party(name='Party')
    >>> tax_identifier = party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES00000000T'
    >>> party.es_province_code = '25'
    >>> party.save()
    >>> supplier = Party(name='Intracomunitary Supplier')
    >>> supplier.save()

Create invoices::

    >>> Tax = Model.get('account.tax')
    >>> customer_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21% (bienes)'),
    ...     ])
    >>> supplier_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'purchase'),
    ...     ('name', '=', 'IVA Intracomunitario 21% (bienes)'),
    ...     ])
    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> invoice.currency = eur
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.taxes.append(customer_tax)
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('242.00')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = supplier
    >>> invoice.currency = eur
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.account = expense
    >>> line.taxes.append(supplier_tax)
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('100.00')

EC Operation and VATList report uses company currency::

    >>> VatList = Model.get('account.reporting.vat_list_es')
    >>> context = {
    ...     'company': company.id,
    ...     'date': today,
    ...     }
    >>> with config.set_context(context):
    ...     record, = VatList.find([])
    >>> assertEqual(record.party, party)
    >>> record.amount
    Decimal('121.00')
    >>> ECOperationList = Model.get('account.reporting.es_ec_operation_list')
    >>> context = {
    ...     'company': company.id,
    ...     'start_date': today,
    ...     'end_date': today,
    ...     }
    >>> with config.set_context(context):
    ...     record, = ECOperationList.find([])
    >>> assertEqual(record.party, supplier)
    >>> record.amount
    Decimal('50.00')
    >>> VatBook = Model.get('account.reporting.vat_book_es')
    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'es_vat_book_type': 'E',
    ...     }
    >>> with config.set_context(context):
    ...     record, = VatBook.find([])
    >>> assertEqual(record.party, party)
    >>> record.base_amount
    Decimal('100.00')
    >>> record.tax_amount
    Decimal('21.00')
