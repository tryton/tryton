====================================
Product Cost FIFO Warehouse Scenario
====================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate product_cost_warehouse::

    >>> config = activate_modules(
    ...     ['product_cost_warehouse', 'product_cost_fifo'])

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
    >>> template.cost_price_method = 'fifo'
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
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])


Make 2 unit of product available @ 100 on 1st warehouse::

    >>> StockMove = Model.get('stock.move')
    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 2
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

Make 2 unit of product available @ 80 in both warehouses::

    >>> moves = []
    >>> for warehouse in [warehouse1, warehouse2]:
    ...     move = StockMove()
    ...     move.product = product
    ...     move.quantity = 2
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

Sent 3 unit of product from 1st warehouse::

    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 3
    >>> move.from_location = warehouse1.storage_location
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('150')
    >>> move.currency = company.currency
    >>> move.click('do')
    >>> move.cost_price
    Decimal('93.3333')

Recompute cost price for both warehouses::

    >>> for warehouse in [warehouse1, warehouse2]:
    ...     with config.set_context(warehouse=warehouse.id):
    ...         recompute = Wizard('product.recompute_cost_price', [product])
    ...         recompute.execute('recompute')

Check cost prices::

    >>> with config.set_context(warehouse=warehouse1.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('80.0001')

    >>> with config.set_context(warehouse=warehouse2.id):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('80.0000')

Check cost prices on moves::

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('93.3333'), Decimal('80.0000'), Decimal('90.0000'), Decimal('90.0000')]

