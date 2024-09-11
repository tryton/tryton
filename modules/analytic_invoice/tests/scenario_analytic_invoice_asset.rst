=====================================
Analytic Invoice with Assets Scenario
=====================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_asset.tests.tools import add_asset_accounts
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> next_month = today + relativedelta(day=1, month=1)
    >>> next_next_month = next_month + relativedelta(months=1)

Activate modules::

    >>> config = activate_modules(
    ...     ['analytic_invoice', 'account_asset'],
    ...     create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=(today, next_next_month)))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = add_asset_accounts(get_accounts())
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
    >>> supplier_invoice.invoice_date = next_month
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
    >>> create_moves.form.date = next_next_month
    >>> create_moves.execute('create_moves')
    >>> analytic_account.reload()
    >>> analytic_account.debit
    Decimal('100.00')
    >>> analytic_account.credit
    Decimal('0.00')

Update the asset::

    >>> update = Wizard('account.asset.update', [asset])
    >>> update.form.value = Decimal('950.00')
    >>> update.execute('update_asset')
    >>> update.form.date = update.form.next_depreciation_date
    >>> update.execute('create_move')
    >>> analytic_account.reload()
    >>> analytic_account.debit
    Decimal('150.00')
    >>> analytic_account.credit
    Decimal('0.00')

Close the asset::

    >>> asset.click('close')
    >>> analytic_account.reload()
    >>> analytic_account.debit
    Decimal('1000.00')
    >>> analytic_account.credit
    Decimal('0.00')
