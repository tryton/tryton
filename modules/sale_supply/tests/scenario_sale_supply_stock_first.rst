================================
Sale Supply Stock First Scenario
================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('sale_supply')

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('100.0000')
    >>> template.supply_on_sale = 'stock_first'
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Fill warehouse::

    >>> inventory = Inventory()
    >>> inventory.location, = Location.find([('code', '=', 'STO')])
    >>> line = inventory.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Sale 3 products with 5 in stock::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 3
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> line, = sale.lines
    >>> bool(line.purchase_request)
    False
    >>> move, = line.moves
    >>> move.state
    'draft'

Sale 3 products with 2 in stock::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 3
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> line, = sale.lines
    >>> bool(line.purchase_request)
    False
    >>> move, = line.moves
    >>> move.state
    'draft'

Sale 4 products with no stock::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 4
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> line, = sale.lines
    >>> bool(line.purchase_request)
    True
    >>> move, = line.moves
    >>> move.state
    'staging'
