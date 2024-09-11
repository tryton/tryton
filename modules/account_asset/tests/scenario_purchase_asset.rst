=======================
Purchase Asset Scenario
=======================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_asset.tests.tools import add_asset_accounts
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['account_asset', 'purchase'], create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = add_asset_accounts(get_accounts())
    >>> revenue = accounts['revenue']
    >>> asset_account = accounts['asset']
    >>> expense = accounts['expense']
    >>> depreciation_account = accounts['depreciation']

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.account_asset = asset_account
    >>> account_category.account_depreciation = depreciation_account
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> asset_template = ProductTemplate()
    >>> asset_template.name = 'Asset'
    >>> asset_template.type = 'assets'
    >>> asset_template.default_uom = unit
    >>> asset_template.list_price = Decimal('1000')
    >>> asset_template.depreciable = True
    >>> asset_template.purchasable = True
    >>> asset_template.account_category = account_category
    >>> asset_template.depreciation_duration = 24
    >>> asset_template.save()
    >>> service_product, = asset_template.products
    >>> asset_product, = asset_template.products
    >>> service_template = ProductTemplate()
    >>> service_template.name = 'Service'
    >>> service_template.type = 'service'
    >>> service_template.default_uom = unit
    >>> service_template.list_price = Decimal('10')
    >>> service_template.purchasable = True
    >>> service_template.account_category = account_category
    >>> service_template.save()
    >>> service_product, = service_template.products

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Purchase an asset mixed with services::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> line = purchase.lines.new()
    >>> line.product = asset_product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('500.0000')
    >>> line = purchase.lines.new()
    >>> line.product = service_product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('5.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> invoice, = purchase.invoices
    >>> asset_line, service_line = invoice.lines
    >>> assertEqual(asset_line.account, asset_account)
    >>> assertEqual(service_line.account, expense)
