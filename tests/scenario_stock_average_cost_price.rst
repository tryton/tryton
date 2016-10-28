========================
Stock Average Cost Price
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

Install stock Module::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price = Decimal('80')
    >>> template.cost_price_method = 'average'
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> negative_product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Negative Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('28')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'average'
    >>> template.save()
    >>> negative_product.template = template
    >>> negative_product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Make 1 unit of the product available @ 100 ::

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

Check Cost Price is 100::

    >>> product.reload()
    >>> product.template.cost_price
    Decimal('100.0000')

Add 1 more unit @ 200::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('200')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Check Cost Price Average is 150::

    >>> product.reload()
    >>> product.template.cost_price
    Decimal('150.0000')

Add twice 1 more unit @ 200::

    >>> incoming_moves = []
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('200')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.save()
    >>> incoming_moves.append(incoming_move)

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('200')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.save()
    >>> incoming_moves.append(incoming_move)

    >>> StockMove.click(incoming_moves, 'do')

Check Cost Price Average is 175::

    >>> product.reload()
    >>> product.template.cost_price
    Decimal('175.0000')

Change Cost Price to 125, to force to write recomputed price later::

    >>> product.template.cost_price = Decimal('125.0000')
    >>> product.template.save()
    >>> product.template.cost_price
    Decimal('125.0000')

Recompute Cost Price::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> product.template.cost_price
    Decimal('175.0000')

Send one product we dont have in stock::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = negative_product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.effective_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.click('do')

Recieve two units of the product with negative stock::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = negative_product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 2
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('2')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Cost price should be set to 2::

    >>> negative_product.template.cost_price
    Decimal('2.0000')
