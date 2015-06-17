========================
Stock Inventory Scenario
========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module')
    >>> stock_module, = Module.find([('name', '=', 'stock')])
    >>> stock_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price = Decimal('80')
    >>> template.cost_price_method = 'average'
    >>> template.save()
    >>> product, = template.products

    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> template2 = ProductTemplate()
    >>> template2.name = 'Product'
    >>> template2.default_uom = kg
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal('140')
    >>> template2.cost_price = Decimal('60')
    >>> template2.cost_price_method = 'average'
    >>> template2.save()
    >>> product2, = template2.products

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
    >>> line_p2.quantity
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
    >>> line_p2.quantity
    3.8

Confirm the inventory::

    >>> inventory.click('confirm')
    >>> line_p1.reload()
    >>> move, = line_p1.moves
    >>> move.quantity
    1.0
    >>> move.from_location == inventory.lost_found
    True
    >>> move.to_location == inventory.location
    True
    >>> line_p2.reload()
    >>> len(line_p2.moves)
    0

Empty storage::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 3
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.effective_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('100')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_moves = [outgoing_move]

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product2
    >>> outgoing_move.uom = kg
    >>> outgoing_move.quantity = 3.8
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.effective_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('140')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_moves.append(outgoing_move)
    >>> StockMove.click(outgoing_moves, 'do')

Create an inventory that should be empty after completion::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.click('complete_lines')
    >>> len(inventory.lines)
    0
