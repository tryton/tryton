=================================================
Account Stock Continental Move Cancelled Scenario
=================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_stock_continental.tests.tools import (
    ...     add_stock_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     'account_stock_continental', create_company, create_chart)

    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> StockMove = Model.get('stock.move')
    >>> StockLocation = Model.get('stock.location')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.account_stock_method = 'continental'
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = add_stock_accounts(get_accounts())
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> stock = accounts['stock']
    >>> stock_in = accounts['stock_expense']
    >>> stock_out, = stock_in.duplicate()

Get stock locations::

    >>> supplier_loc, = StockLocation.find([('code', '=', 'SUP')])
    >>> storage_loc, = StockLocation.find([('code', '=', 'STO')])

Create product category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.account_stock = stock
    >>> account_category.account_stock_in = stock_in
    >>> account_category.account_stock_out = stock_out
    >>> account_category.save()

Create product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom, = ProductUom.find([('name', '=', "Unit")])
    >>> template.type = 'goods'
    >>> template.cost_price_method = 'fixed'
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('10.0000')
    >>> product.save()

Receive product::

    >>> stock_move = StockMove()
    >>> stock_move.product = product
    >>> stock_move.from_location = supplier_loc
    >>> stock_move.to_location = storage_loc
    >>> stock_move.quantity = 1
    >>> stock_move.unit_price = Decimal('10.0000')
    >>> stock_move.currency = get_currency()
    >>> stock_move.click('do')
    >>> stock_move.state
    'done'
    >>> account_move, = stock_move.account_moves
    >>> account_move.state
    'posted'
    >>> stock.reload()
    >>> stock.balance
    Decimal('10.00')

Cancel reception::

    >>> stock_move.click('cancel')
    >>> stock_move.state
    'cancelled'
    >>> len(stock_move.account_moves)
    2
    >>> assertEqual([m.state for m in stock_move.account_moves], ['posted', 'posted'])
    >>> stock.reload()
    >>> stock.balance
    Decimal('0.00')
