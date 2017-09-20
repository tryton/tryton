=======================
Purchase Asset Scenario
=======================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.account_asset.tests.tools \
    ...     import add_asset_accounts
    >>> today = datetime.date.today()

Install account_asset::

    >>> config = activate_modules(['account_asset', 'purchase'])

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
    >>> asset_template.account_expense = expense
    >>> asset_template.account_revenue = revenue
    >>> asset_template.account_asset = asset_account
    >>> asset_template.account_depreciation = depreciation_account
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
    >>> service_template.account_expense = expense
    >>> service_template.account_revenue = revenue
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
    >>> line = purchase.lines.new()
    >>> line.product = service_product
    >>> line.quantity = 1
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> invoice, = purchase.invoices
    >>> asset_line, service_line = invoice.lines
    >>> asset_line.account == asset_account
    True
    >>> service_line.account == expense
    True
