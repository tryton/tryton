=============================
Account ES Reporting Scenario
=============================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts, create_fiscalyear)
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
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
    ...     create_fiscalyear(company, datetime.date(2018, 1, 1)))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company, 'account_es.pgc_0_pyme')
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']

Create parties::

    >>> Country = Model.get('country.country')
    >>> spain = Country(name='Spain', code='ES')
    >>> spain.save()
    >>> Party = Model.get('party.party')
    >>> TaxRule = Model.get('account.tax.rule')
    >>> party = Party(name='Party')
    >>> tax_identifier = party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES00000000T'
    >>> address, = party.addresses
    >>> address.country = spain
    >>> address.zip = '25001'
    >>> party.es_province_code
    '25'
    >>> party.save()
    >>> tax_rule, = TaxRule.find([
    ...     ('company', '=', company.id),
    ...     ('kind', '=', 'purchase'),
    ...     ('name', '=', 'Retención IRPF 15%'),
    ...     ])
    >>> supplier = Party(name='Supplier')
    >>> supplier.supplier_tax_rule = tax_rule
    >>> tax_identifier = supplier.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'ES00000001R'
    >>> supplier.es_province_code = '08'
    >>> supplier.save()
    >>> tax_rule, = TaxRule.find([
    ...     ('company', '=', company.id),
    ...     ('kind', '=', 'purchase'),
    ...     ('name', '=', 'Compras Intracomunitarias'),
    ...     ])
    >>> ec_supplier = Party(name='Intracomunitary Supplier')
    >>> ec_supplier.supplier_tax_rule = tax_rule
    >>> tax_identifier = ec_supplier.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'BE0897290877'
    >>> ec_supplier.save()

Create account category::

    >>> Tax = Model.get('account.tax')
    >>> customer_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('group.kind', '=', 'sale'),
    ...     ('name', '=', 'IVA 21% (bienes)'),
    ...     ])
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
    >>> account_category.customer_taxes.append(customer_tax)
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

Create invoices::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('242.00')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = supplier
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('106.00')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = ec_supplier
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('100.00')

Generate aeat reports::

    >>> Period = Model.get('account.period')
    >>> aeat = Wizard('account.reporting.aeat')
    >>> aeat.form.report = '111'
    >>> aeat.form.periods.append(Period(period.id))
    >>> aeat.execute('choice')
    >>> extension, content, _, name = aeat.actions[0]
    >>> extension
    'txt'
    >>> with file_open('account_es/tests/111.txt') as f:
    ...     content == f.read()
    True
    >>> name
    'AEAT Model 111'

    >>> aeat = Wizard('account.reporting.aeat')
    >>> aeat.form.report = '115'
    >>> period = Period(period.id)
    >>> aeat.form.periods.append(Period(period.id))
    >>> aeat.execute('choice')
    >>> extension, content, _, name = aeat.actions[0]
    >>> extension
    'txt'
    >>> with file_open('account_es/tests/115.txt') as f:
    ...     content == f.read()
    True
    >>> name
    'AEAT Model 115'

    >>> aeat = Wizard('account.reporting.aeat')
    >>> aeat.form.report = '303'
    >>> aeat.form.periods.append(Period(period.id))
    >>> aeat.execute('choice')
    >>> extension, content, _, name = aeat.actions[0]
    >>> extension
    'txt'
    >>> with file_open('account_es/tests/303.txt') as f:
    ...     content == f.read()
    True
    >>> name
    'AEAT Model 303'

    >>> VatList = Model.get('account.reporting.vat_list_es')
    >>> context = {
    ...     'company': company.id,
    ...     'date': period.end_date,
    ...     }
    >>> with config.set_context(context):
    ...     vat_list_records = VatList.find([])
    ...     report = Report('account.reporting.aeat347')
    ...     extension, content, _, name = report.execute(vat_list_records)
    >>> extension
    'txt'
    >>> with file_open('account_es/tests/347.txt') as f:
    ...     content == f.read()
    True
    >>> name.startswith('AEAT Model 347')
    True

    >>> ECOperationList = Model.get('account.reporting.es_ec_operation_list')
    >>> context = {
    ...     'company': company.id,
    ...     'start_date': period.start_date,
    ...     'end_date': period.end_date,
    ...     }
    >>> with config.set_context(context):
    ...     records = ECOperationList.find([])
    ...     report = Report('account.reporting.aeat349')
    ...     extension, content, _, name = report.execute(records)
    >>> extension
    'txt'
    >>> with file_open('account_es/tests/349.txt') as f:
    ...     content == f.read()
    True
    >>> name.startswith('AEAT Model 349')
    True
