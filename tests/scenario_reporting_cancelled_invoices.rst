================================================
Account ES Reporting Cancelled Invoices Scenario
================================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

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
    ...     create_fiscalyear(company))
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
    ...        ('type.%s' % kind , '=', True),
    ...        ('company', '=', company.id),
    ...        ], limit=1)
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']
    >>> create_chart.form.account_receivable = accounts['receivable']
    >>> create_chart.form.account_payable = accounts['payable']
    >>> create_chart.execute('create_properties')

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> Tax = Model.get('account.tax')
    >>> supplier_tax, = Tax.find([
    ...     ('company', '=', company.id),
    ...     ('name', '=', 'IVA 21% (operaciones corrientes)'),
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

Compute VAT LIST report::

    >>> VatList = Model.get('account.reporting.vat_list_es')
    >>> context = {
    ...     'company': company.id,
    ...     'date': period.end_date,
    ...     }
    >>> with config.set_context(context):
    ...     vat_list_records = VatList.find([])
    >>> len(vat_list_records)
    1

Refund the invoice::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.form.invoice_date = invoice.invoice_date
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    'cancel'

VAT List is empty::

    >>> with config.set_context(context):
    ...     vat_list_records = VatList.find([])
    >>> len(vat_list_records)
    0

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
    >>> with config.set_context(context):
    ...     vat_list_records = VatList.find([])
    >>> len(vat_list_records)
    1

Cancel the invoice and check VAT List is empty::

    >>> invoice.click('cancel')
    >>> invoice.state
    'cancel'
    >>> with config.set_context(context):
    ...     vat_list_records = VatList.find([])
    >>> len(vat_list_records)
    0
