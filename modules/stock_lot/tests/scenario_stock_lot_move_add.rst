===========================
Stock Lot Move Add Scenario
===========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate modules::

    >>> config = activate_modules('stock_lot')

Create company::

    >>> _ = create_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create a move::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.unit_price = Decimal('20')
    >>> move.save()

Create a lot::

    >>> Lot = Model.get('stock.lot')
    >>> lot2 = Lot(number='02', product=product)
    >>> lot2.save()

Add few lots::

    >>> add_lots = Wizard('stock.move.add.lots', [move])
    >>> add_lots.form.product== product
    True
    >>> add_lots.form.quantity
    10.0
    >>> add_lots.form.unit == unit
    True
    >>> add_lots.form.quantity_remaining
    10.0

    >>> lot = add_lots.form.lots.new()
    >>> lot.quantity
    10.0
    >>> lot.number = '01'
    >>> lot.quantity = 2
    >>> lot = add_lots.form.lots.new()
    >>> lot.quantity
    8.0
    >>> lot.number = '02'
    >>> lot.quantity = 1

    >>> add_lots.execute('add')

Check moves::

    >>> move, = Move.find([('lot.number', '=', '01')])
    >>> move.quantity
    2.0
    >>> move, = Move.find([('lot.number', '=', '02')])
    >>> move.quantity
    1.0
    >>> move.lot == lot2
    True
    >>> move, = Move.find([('lot', '=', None)])
    >>> move.quantity
    7.0

Add lot to remaining::

    >>> add_lots = Wizard('stock.move.add.lots', [move])
    >>> lot = add_lots.form.lots.new()
    >>> lot.number = '03'
    >>> add_lots.execute('add')

    >>> len(Move.find([]))
    3
    >>> move.lot.number
    '03'
    >>> move.quantity
    7.0
