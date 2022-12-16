=====================
Stock FIFO Cost Price
=====================

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

    >>> config = activate_modules('product_cost_fifo')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'fifo'
    >>> product, = template.products
    >>> product.cost_price = Decimal('80')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> production_loc = Location(name="Production", type='production')
    >>> production_loc.save()

Make 4 units of the product available @ 10 ::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 4
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('10')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Check Cost Price is 10::

    >>> product.reload()
    >>> product.cost_price
    Decimal('10.0000')

Add 2 more units @ 25 from production::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 2
    >>> incoming_move.from_location = production_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('25')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Check Cost Price FIFO is 15::

    >>> product.reload()
    >>> product.cost_price
    Decimal('15.0000')

Sell 3 units @ 50::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 3
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('50')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.click('do')

Check Cost Price FIFO is 20 and cost is 10::

    >>> product.reload()
    >>> product.cost_price
    Decimal('20.0000')
    >>> outgoing_move.cost_price
    Decimal('10.0000')

Sell twice 1 more units @ 50::

    >>> outgoing_moves = []
    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('50')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.save()
    >>> outgoing_moves.append(outgoing_move)

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('50')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.save()
    >>> outgoing_moves.append(outgoing_move)

    >>> StockMove.click(outgoing_moves, 'do')

Check Cost Price FIFO is 25 and costs are 10 and 25::

    >>> product.reload()
    >>> product.cost_price
    Decimal('25.0000')
    >>> [m.cost_price for m in outgoing_moves]
    [Decimal('10.0000'), Decimal('25.0000')]
