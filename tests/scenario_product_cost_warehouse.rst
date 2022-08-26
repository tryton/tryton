===============================
Product Cost Warehouse Scenario
===============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('product_cost_warehouse')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> product, = template.products
    >>> template.save()
    >>> product, = template.products

Set cost per warehouse::

    >>> ProductConfiguration = Model.get('product.configuration')
    >>> product_config = ProductConfiguration(1)
    >>> product_config.cost_price_warehouse = True
    >>> product_config.save()


Create stock locations::

    >>> Location = Model.get('stock.location')
    >>> StockConfiguration = Model.get('stock.configuration')
    >>> warehouse1, = Location.find([('code', '=', 'WH')])
    >>> warehouse2, = warehouse1.duplicate(default={'name': "Warhouse bis"})
    >>> transit = Location(name="Transit", type='storage')
    >>> transit.save()
    >>> stock_config = StockConfiguration(1)
    >>> stock_config.shipment_internal_transit = transit
    >>> stock_config.save()
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])


Make 1 unit of product available @ 100 on 1st warehouse::

    >>> StockMove = Model.get('stock.move')
    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = warehouse1.storage_location
    >>> move.unit_price = Decimal('100')
    >>> move.currency = company.currency
    >>> move.click('do')

Check cost prices::

    >>> with config.set_context(warehouse=warehouse1.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('100.0000')

    >>> with config.set_context(warehouse=warehouse2.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('0')

Make 1 unit of product available @ 80 in both warehouses::

    >>> moves = []
    >>> for warehouse in [warehouse1, warehouse2]:
    ...     move = StockMove()
    ...     move.product = product
    ...     move.quantity = 1
    ...     move.from_location = supplier_loc
    ...     move.to_location = warehouse.storage_location
    ...     move.unit_price = Decimal('80')
    ...     moves.append(move)
    >>> StockMove.click(moves, 'do')

Check cost prices::

    >>> with config.set_context(warehouse=warehouse1.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('90.0000')

    >>> with config.set_context(warehouse=warehouse2.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('80.0000')

Recompute cost price for both warehouses::

    >>> for warehouse in [warehouse1, warehouse2]:
    ...     with config.set_context(warehouse=warehouse.id):
    ...         recompute = Wizard('product.recompute_cost_price', [product])
    ...         recompute.execute('recompute')

Check cost prices::

    >>> with config.set_context(warehouse=warehouse1.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('90.0000')

    >>> with config.set_context(warehouse=warehouse2.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('80.0000')

Check cost prices on moves::

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('80.0000'), Decimal('90.0000'), Decimal('90.0000')]

Forbid direct move between warehouses::

    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = warehouse1.storage_location
    >>> move.to_location = warehouse2.storage_location
    >>> move.unit_price = product.cost_price
    >>> move.save()
    >>> move.click('do')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    MoveValidationError: ...

    >>> move.to_location = transit
    >>> move.click('do')
    >>> move.state
    'done'

Transfer 1 product between warehouses::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> shipment = ShipmentInternal()
    >>> shipment.from_location = warehouse1.storage_location
    >>> shipment.to_location = warehouse2.storage_location
    >>> move = shipment.moves.new()
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.unit_price = product.cost_price
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_force')
    >>> shipment.state
    'assigned'

    >>> shipment.click('ship')
    >>> shipment.state
    'shipped'
    >>> move, = shipment.outgoing_moves
    >>> move.state
    'done'
    >>> move.cost_price
    Decimal('90.0000')

    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> move, = shipment.incoming_moves
    >>> move.state
    'done'
    >>> move.cost_price
    Decimal('85.0000')

Recompute cost price for both warehouses::

    >>> for warehouse in [warehouse1, warehouse2]:
    ...     with config.set_context(warehouse=warehouse.id):
    ...         recompute = Wizard('product.recompute_cost_price', [product])
    ...         recompute.execute('recompute')

Check cost prices::

    >>> with config.set_context(warehouse=warehouse1.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('90.0000')

    >>> with config.set_context(warehouse=warehouse2.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('85.0000')
