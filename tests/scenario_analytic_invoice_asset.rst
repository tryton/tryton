=====================================
Analytic Invoice with Assets Scenario
=====================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.account_asset.tests.tools \
    ...     import add_asset_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules(['analytic_invoice', 'account_asset'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = add_asset_accounts(get_accounts(company), company)
    >>> revenue = accounts['revenue']
    >>> asset_account = accounts['asset']
    >>> expense = accounts['expense']
    >>> depreciation_account = accounts['depreciation']

Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.account_asset = asset_account
    >>> account_category.account_depreciation = depreciation_account
    >>> account_category.save()

Create an asset::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> asset_template = ProductTemplate()
    >>> asset_template.name = 'Asset'
    >>> asset_template.type = 'assets'
    >>> asset_template.default_uom = unit
    >>> asset_template.list_price = Decimal('1000')
    >>> asset_template.account_category = account_category
    >>> asset_template.depreciable = True
    >>> asset_template.depreciation_duration = 10
    >>> asset_template.save()
    >>> asset_product, = asset_template.products

Buy an asset::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> supplier_invoice = Invoice(type='in')
    >>> supplier_invoice.party = supplier
    >>> invoice_line = supplier_invoice.lines.new()
    >>> invoice_line.product = asset_product
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('1000')
    >>> entry, = invoice_line.analytic_accounts
    >>> entry.account = analytic_account
    >>> supplier_invoice.invoice_date = today + relativedelta(day=1, month=1)
    >>> supplier_invoice.click('post')
    >>> supplier_invoice.state
    'posted'
    >>> invoice_line, = supplier_invoice.lines
    >>> analytic_account.debit
    Decimal('0.00')
    >>> analytic_account.credit
    Decimal('0.00')

Depreciate the asset::

    >>> Asset = Model.get('account.asset')
    >>> asset = Asset()
    >>> asset.product = asset_product
    >>> asset.supplier_invoice_line = invoice_line
    >>> asset.residual_value = Decimal(0)
    >>> asset.click('create_lines')
    >>> asset.click('run')

Create Moves for 1 month::

    >>> create_moves = Wizard('account.asset.create_moves')
    >>> create_moves.form.date = (supplier_invoice.invoice_date
    ...     + relativedelta(months=1))
    >>> create_moves.execute('create_moves')
    >>> analytic_account.reload()
    >>> analytic_account.debit
    Decimal('100.00')
    >>> analytic_account.credit
    Decimal('0.00')
