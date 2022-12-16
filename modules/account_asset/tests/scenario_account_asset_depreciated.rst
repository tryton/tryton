==================================
Account Asset Depreciated Scenario
==================================

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
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.account_asset.tests.tools \
    ...     import add_asset_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_asset')

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
    >>> asset_template.depreciation_duration = 24
    >>> asset_template.save()
    >>> asset_product, = asset_template.products

Depreciate the asset::

    >>> Asset = Model.get('account.asset')
    >>> asset = Asset()
    >>> asset.product = asset_product
    >>> asset.value = Decimal('1500.00')
    >>> asset.depreciated_amount = Decimal('500.00')
    >>> asset.start_date = today + relativedelta(day=1, month=1)
    >>> asset.purchase_date = asset.start_date
    >>> asset.end_date = (asset.start_date +
    ...     relativedelta(years=2, days=-1))
    >>> asset.quantity = 1
    >>> asset.residual_value = Decimal('100')
    >>> asset.click('create_lines')
    >>> len(asset.lines)
    24
    >>> [l.depreciation for l in asset.lines] == [Decimal('37.5')] * 24
    True
    >>> [l.acquired_value for l in asset.lines] == [Decimal('1500.00')] * 24
    True
    >>> [l.depreciable_basis for l in asset.lines] == [Decimal('900.00')] * 24
    True
    >>> asset.lines[0].actual_value
    Decimal('962.50')
    >>> asset.lines[0].accumulated_depreciation
    Decimal('537.50')
    >>> asset.lines[11].actual_value
    Decimal('550.00')
    >>> asset.lines[11].accumulated_depreciation
    Decimal('950.00')
    >>> asset.lines[-1].actual_value
    Decimal('100.00')
    >>> asset.lines[-1].accumulated_depreciation
    Decimal('1400.00')
    >>> asset.click('run')

Create Moves for 3 months::

    >>> create_moves = Wizard('account.asset.create_moves')
    >>> create_moves.form.date = (asset.start_date
    ...     + relativedelta(months=3))
    >>> create_moves.execute('create_moves')
    >>> depreciation_account.reload()
    >>> depreciation_account.debit
    Decimal('0.00')
    >>> depreciation_account.credit
    Decimal('112.50')
    >>> expense.reload()
    >>> expense.debit
    Decimal('112.50')
    >>> expense.credit
    Decimal('0.00')

Close the asset::

    >>> asset.click('close')
    >>> asset_account.reload()
    >>> asset_account.debit
    Decimal('0.00')
    >>> asset_account.credit
    Decimal('1500.00')
    >>> depreciation_account.reload()
    >>> depreciation_account.debit
    Decimal('612.50')
    >>> depreciation_account.credit
    Decimal('112.50')
    >>> revenue.reload()
    >>> revenue.debit
    Decimal('887.50')
    >>> revenue.credit
    Decimal('0.00')
