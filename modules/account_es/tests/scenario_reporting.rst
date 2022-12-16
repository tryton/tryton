=============================
Account ES Reporting Scenario
=============================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Install account_es::

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

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> ModelData = Model.get('ir.model.data')
    >>> data, = ModelData.find([
    ...        ('module', '=', 'account_es'),
    ...        ('fs_id', '=', 'pgc_0_pyme'),
    ...        ], limit=1)
    >>> account_template = AccountTemplate(data.db_id)
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> accounts = {}
    >>> for kind in ['receivable', 'payable', 'revenue', 'expense']:
    ...     accounts[kind], = Account.find([
    ...        ('kind', '=', kind),
    ...        ('company', '=', company.id),
    ...        ], limit=1)
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']
    >>> create_chart.form.account_receivable = accounts['receivable']
    >>> create_chart.form.account_payable = accounts['payable']
    >>> create_chart.execute('create_properties')

Create parties::

    >>> Party = Model.get('party.party')
    >>> TaxRule = Model.get('account.tax.rule')
    >>> party = Party(name='Party')
    >>> party.save()
    >>> tax_rule, = TaxRule.find([
    ...     ('company', '=', company.id),
    ...     ('kind', '=', 'purchase'),
    ...     ('name', '=', 'Retención IRPF 15%'),
    ...     ])
    >>> supplier = Party(name='Supplier')
    >>> supplier.supplier_tax_rule = tax_rule
    >>> supplier.save()

Create account category::

    >>> Tax = Model.get('account.tax')
    >>> customer_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('name', '=', 'IVA 21%'),
    ...     ])
    >>> supplier_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('name', '=', 'IVA 21% (operaciones corrientes)'),
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
