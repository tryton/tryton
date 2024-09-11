===========================================
Sale Supply Production Stock First Scenario
===========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'sale_supply_production', create_company, create_chart)

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> UoM = Model.get('product.uom')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = UoM.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.salable = True
    >>> template.supply_on_sale = 'stock_first'
    >>> template.list_price = Decimal(30)
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal(20)
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

Sale 3 products without production request::

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
    >>> len(line.productions)
    0
    >>> move, = line.moves
    >>> move.state
    'draft'

Sale 4 products with production request::

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
    >>> len(line.productions)
    1
    >>> move, = line.moves
    >>> move.state
    'staging'
