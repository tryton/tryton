=========================================
Account ES Compensated Reporting Scenario
=========================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from functools import partial

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     ['account_es', 'account_invoice'],
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
    ...         today=(dt.date(2018, 1, 1), dt.date(2018, 12, 31))))
    >>> fiscalyear.click('create_period')
    >>> previous_period = fiscalyear.periods[0]
    >>> period = fiscalyear.periods[1]

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
    >>> customer_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21% (bienes)'),
    ...     ])
    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(customer_tax)
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
    >>> invoice.party = party
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('50')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('60.50')

Create previous period compensation move::

    >>> Account = Model.get('account.account')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])
    >>> compensation_account, = Account.find([
    ...         ('company', '=', company.id),
    ...         ('code', '=', '4700'),
    ...         ])
    >>> move = Move()
    >>> move.period = previous_period
    >>> move.journal = journal_cash
    >>> move.date = previous_period.start_date
    >>> line = move.lines.new()
    >>> line.account = expense
    >>> line.credit = Decimal(40)
    >>> line = move.lines.new()
    >>> line.account = compensation_account
    >>> line.debit = Decimal(40)
    >>> move.click('post')


Generate aeat 303 report::

    >>> aeat = Wizard('account.reporting.aeat')
    >>> aeat.form.report = '303'
    >>> aeat.form.start_period = period
    >>> aeat.form.end_period = period
    >>> aeat.execute('choice')
    >>> extension, content, _, name = aeat.actions[0]
    >>> extension
    'txt'
    >>> with file_open('account_es/tests/303_compensate.txt') as f:
    ...     assertEqual(content, f.read())
    >>> name
    'AEAT Model 303-2018-02'
