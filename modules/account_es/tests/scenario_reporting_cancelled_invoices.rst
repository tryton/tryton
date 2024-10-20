================================================
Account ES Reporting Cancelled Invoices Scenario
================================================

Imports::

    >>> from decimal import Decimal
    >>> from functools import partial

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

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
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> Tax = Model.get('account.tax')
    >>> supplier_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'purchase'),
    ...     ('name', '=', 'IVA 21% (bienes)'),
    ...     ])
    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.supplier_taxes.append(supplier_tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')

Compute reports::

    >>> VatList = Model.get('account.reporting.vat_list_es')
    >>> VatBook = Model.get('account.reporting.vat_book_es')
    >>> vat_list_context = {
    ...     'company': company.id,
    ...     'date': period.end_date,
    ...     }
    >>> with config.set_context(vat_list_context):
    ...     vat_list_records = VatList.find([])
    >>> len(vat_list_records)
    1
    >>> vat_book_context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'es_vat_book_type': 'R',
    ...     }
    >>> with config.set_context(vat_book_context):
    ...     vat_book_records = VatBook.find([])
    >>> len(vat_book_records)
    1

Refund the invoice::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.form.invoice_date = invoice.invoice_date
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    'cancelled'

Check reports::

    >>> with config.set_context(vat_list_context):
    ...     vat_list_records = VatList.find([])
    >>> vat_list_record, = vat_list_records
    >>> vat_list_record.amount
    Decimal('0.00')
    >>> with config.set_context(vat_book_context):
    ...     vat_book_records = VatBook.find([])
    >>> len(vat_book_records)
    2

Create another invoice::

    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> with config.set_context(vat_list_context):
    ...     vat_list_records = VatList.find([])
    >>> vat_list_record, = vat_list_records
    >>> vat_list_record.amount
    Decimal('242.00')
    >>> with config.set_context(vat_book_context):
    ...     vat_book_records = VatBook.find([])
    >>> len(vat_book_records)
    3

Cancel the invoice and check reports::

    >>> invoice.click('cancel')
    >>> invoice.state
    'cancelled'
    >>> with config.set_context(vat_list_context):
    ...     vat_list_records = VatList.find([])
    >>> vat_list_record, = vat_list_records
    >>> vat_list_record.amount
    Decimal('0.00')
    >>> with config.set_context(vat_book_context):
    ...     vat_book_records = VatBook.find([])
    >>> len(vat_book_records)
    2
