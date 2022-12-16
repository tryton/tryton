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

Activate modules::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
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

    >>> template = ProductTemplate()
    >>> template.name = 'Negative Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('28')
    >>> template.cost_price_method = 'average'
    >>> negative_product, = template.products
    >>> negative_product.cost_price = Decimal('5.0000')
    >>> template.save()
    >>> negative_product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> storage_sub_loc = Location(
    ...     name="Storage Sub", type='storage', parent=storage_loc)
    >>> storage_sub_loc.save()
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Make 1 unit of the product available @ 100 ::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_sub_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Check Cost Price is 100::

    >>> product.reload()
    >>> product.cost_price
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
    >>> product.cost_price
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
    >>> product.cost_price
    Decimal('175.0000')

Reduce Cost Price by 80%, to force to write recomputed price later::

    >>> modify_cost_price = Wizard('product.modify_cost_price', [product])
    >>> modify_cost_price.form.cost_price = 'cost_price * 0.8'
    >>> modify_cost_price.form.date = today + datetime.timedelta(days=1)
    >>> modify_cost_price.execute('modify')
    >>> product.cost_price
    Decimal('140.0000')

Increase Cost Price by 10% using Template wizard::

    >>> modify_cost_price = Wizard(
    ...     'product.modify_cost_price', [product.template])
    >>> modify_cost_price.form.cost_price = 'cost_price * 1.1'
    >>> modify_cost_price.form.date = today + datetime.timedelta(days=1)
    >>> modify_cost_price.execute('modify')
    >>> product.reload()
    >>> product.cost_price
    Decimal('154.0000')

Send one product we don't have in stock::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = negative_product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.unit_price = Decimal('28')
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.effective_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.click('do')

Cost price should stay 5::

    >>> negative_product.cost_price
    Decimal('5.0000')

Return one product to the supplier::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = negative_product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.unit_price = Decimal('28')
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = supplier_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.effective_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.click('do')

Cost price should stay 5::

    >>> negative_product.cost_price
    Decimal('5.0000')

Receive one unit of the product with negative stock so the stock stays negative::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = negative_product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> outgoing_move.unit_price = Decimal('28')
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('3')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Cost price should be set to last unit price::

    >>> negative_product.reload()
    >>> negative_product.cost_price
    Decimal('3.0000')

Receive two units of the product so the stock becomes positive::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = negative_product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 2
    >>> outgoing_move.unit_price = Decimal('28')
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('2')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Cost price should be set to last unit price::

    >>> negative_product.reload()
    >>> negative_product.cost_price
    Decimal('2.0000')

Recompute Cost Price::

    >>> recompute = Wizard('product.recompute_cost_price', [negative_product])
    >>> recompute.execute('recompute')
    >>> negative_product.cost_price
    Decimal('2.0000')
