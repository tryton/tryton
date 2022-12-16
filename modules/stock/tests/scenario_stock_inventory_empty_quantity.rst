=======================================
Stock Inventory Scenario Empty Quantity
=======================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Install stock Module::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

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
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = company.currency
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
    >>> move.from_location == inventory.location
    True
    >>> move.to_location == inventory.lost_found
    True
