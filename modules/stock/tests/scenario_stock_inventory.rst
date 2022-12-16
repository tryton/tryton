========================
Stock Inventory Scenario
========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> lost_found_loc, = Location.find([('type', '=', 'lost_found')])

Create products::

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

    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> template2 = ProductTemplate()
    >>> template2.name = 'Product'
    >>> template2.default_uom = kg
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal('140')
    >>> template2.cost_price_method = 'average'
    >>> product2, = template2.products
    >>> product2.cost_price = Decimal('60')
    >>> template2.save()
    >>> product2, = template2.products

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.consumable = True
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> consumable, = template.products
    >>> consumable.cost_price = Decimal('80')
    >>> template.save()
    >>> consumable, = template.products

Fill storage::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = company.currency
    >>> incoming_moves = [incoming_move]

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product2
    >>> incoming_move.uom = kg
    >>> incoming_move.quantity = 2.5
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('70')
    >>> incoming_move.currency = company.currency
    >>> incoming_moves.append(incoming_move)
    >>> StockMove.click(incoming_moves, 'do')

Create an inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> inventory.save()
    >>> inventory.click('complete_lines')
    >>> line_by_product = {l.product.id: l for l in inventory.lines}
    >>> line_p1 = line_by_product[product.id]
    >>> line_p1.expected_quantity
    1.0
    >>> line_p1.quantity = 3
    >>> line_p2 = line_by_product[product2.id]
    >>> line_p2.expected_quantity
    2.5
    >>> inventory.save()

Fill storage with more quantities::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = company.currency
    >>> incoming_moves = [incoming_move]

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product2
    >>> incoming_move.uom = kg
    >>> incoming_move.quantity = 1.3
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('70')
    >>> incoming_move.currency = company.currency
    >>> incoming_moves.append(incoming_move)
    >>> StockMove.click(incoming_moves, 'do')

Update the inventory::

    >>> inventory.click('complete_lines')
    >>> line_p1.reload()
    >>> line_p1.expected_quantity
    2.0
    >>> line_p1.quantity
    3.0
    >>> line_p2.reload()
    >>> line_p2.expected_quantity
    3.8
    >>> line_p2.quantity = 3.8
    >>> line_p2.save()

Confirm the inventory::

    >>> inventory.click('confirm')
    >>> line_p1.reload()
    >>> line_p1.expected_quantity
    2.0
    >>> move, = line_p1.moves
    >>> move.quantity
    1.0
    >>> move.from_location == lost_found_loc
    True
    >>> move.to_location == inventory.location
    True
    >>> line_p2.reload()
    >>> len(line_p2.moves)
    0

Creating an inventory with empty quantities::

    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> line = inventory.lines.new()
    >>> line.product = product
    >>> inventory.click('confirm')
    >>> line, = inventory.lines
    >>> len(line.moves)
    0

Empty storage::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> line = inventory.lines.new()
    >>> line.product = product
    >>> line.quantity = 0
    >>> line = inventory.lines.new()
    >>> line.product = product2
    >>> line.quantity = 0
    >>> inventory.save()
    >>> line_p1, line_p2 = inventory.lines
    >>> line_p1.quantity
    0.0
    >>> line_p1.expected_quantity
    3.0
    >>> line_p2.quantity
    0.0
    >>> line_p2.expected_quantity
    3.8
    >>> inventory.click('confirm')

Add quantity of consumable product::

    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> line = inventory.lines.new()
    >>> line.product = consumable
    >>> line.quantity = 5.0
    >>> inventory.click('complete_lines')
    >>> len(inventory.lines)
    1
    >>> inventory.click('confirm')
    >>> line, = inventory.lines
    >>> move, = line.moves
    >>> move.quantity
    5.0
    >>> move.from_location == lost_found_loc
    True
    >>> move.to_location == inventory.location
    True

Create an inventory that should be empty after completion::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> inventory.click('complete_lines')
    >>> len(inventory.lines)
    0
