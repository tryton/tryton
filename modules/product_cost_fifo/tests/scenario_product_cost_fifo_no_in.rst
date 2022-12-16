===================================
Stock FIFO Cost Price with no Input
===================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model
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

Make 2 units of the product not available @ 60 and 80 ::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('60')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.fifo_quantity = 1
    >>> incoming_move.click('do')

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('80')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.fifo_quantity = 1
    >>> incoming_move.click('do')

Sell 1 unit @ 200::

    >>> StockMove = Model.get('stock.move')
    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('200')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.click('do')

Check Cost Price FIFO is the current cost price::

    >>> product.reload()
    >>> product.cost_price
    Decimal('70.0000')
    >>> outgoing_move.cost_price
    Decimal('70.0000')
