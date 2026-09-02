==================================
Stock Inventory Variation Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('stock', create_company)
    >>> Location = Model.get('stock.location')
    >>> Inventory = Model.get('stock.inventory')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> StockConfiguration = Model.get('stock.configuration')
    >>> StockMove = Model.get('stock.move')

Get currency::

    >>> currency = get_currency()

Setup tolerance::

    >>> stock_config = StockConfiguration(1)
    >>> stock_config.inventory_quantity_tolerance = 0.1
    >>> stock_config.inventory_cost_thresold = Decimal('200.00')
    >>> stock_config.save()

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> lost_found_loc, = Location.find([('type', '=', 'lost_found')])

Create products::

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

Fill storage::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.unit = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = currency
    >>> incoming_moves = [incoming_move]

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product2
    >>> incoming_move.unit = kg
    >>> incoming_move.quantity = 2.5
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.unit_price = Decimal('70')
    >>> incoming_move.currency = currency
    >>> incoming_moves.append(incoming_move)
    >>> StockMove.click(incoming_moves, 'do')

Create an inventory::

    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> inventory.save()
    >>> inventory.click('complete_lines')
    >>> line_by_product = {l.product.id: l for l in inventory.lines}

    >>> line_p1 = line_by_product[product.id]
    >>> line_p1.expected_quantity
    1.0
    >>> line_p1.quantity = 2
    >>> line_p1.quantity_variation
    1.0
    >>> line_p1.tolerance_quantity_variation
    10.0
    >>> line_p1.cost_variation
    Decimal('100.0000')

    >>> line_p2 = line_by_product[product2.id]
    >>> line_p2.expected_quantity
    2.5
    >>> line_p2.quantity = 5
    >>> line_p2.cost_variation
    Decimal('175.0000')
    >>> line_p2.tolerance_cost_variation
    Decimal('0.8750')

    >>> inventory.click('confirm')
    Traceback (most recent call last):
        ...
    InventoryOverToleranceWarning: ...
