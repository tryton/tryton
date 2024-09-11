=======================================
Stock Inventory Scenario Empty Quantity
=======================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('stock', create_company)

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> lost_found_loc, = Location.find([('type', '=', 'lost_found')])

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> product, = template.products
    >>> product.cost_price = Decimal('80')
    >>> template.save()
    >>> product, = template.products

Fill storage::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.unit = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = get_currency()
    >>> incoming_move.click('do')

Creating an inventory with empty quantities creates and empty move::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'empty'
    >>> inventory.save()
    >>> inventory.click('complete_lines')
    >>> line, = inventory.lines
    >>> line.expected_quantity
    1.0
    >>> line.quantity
    >>> inventory.click('confirm')
    >>> line.reload()
    >>> line.expected_quantity
    1.0
    >>> move, = line.moves
    >>> move.quantity
    1.0
    >>> assertEqual(move.from_location, inventory.location)
    >>> assertEqual(move.to_location, lost_found_loc)
