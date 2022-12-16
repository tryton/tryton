================================
Stock Lot Unit Move Add Scenario
================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate modules::

    >>> config = activate_modules('stock_lot_unit')

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
    >>> move.quantity = 5
    >>> move.unit_price = Decimal('20')
    >>> move.save()

Create a lot::

    >>> Lot = Model.get('stock.lot')
    >>> lot = Lot(number='01', product=product)
    >>> lot.unit = unit
    >>> lot.unit_quantity = 1
    >>> lot.save()

Add a lot::

    >>> add_lots = Wizard('stock.move.add.lots', [move])
    >>> lot = add_lots.form.lots.new()
    >>> lot.quantity
    5.0
    >>> lot.product = product  # proteus does not set reverse domain
    >>> lot.number = '01'
    >>> lot.unit == unit
    True
    >>> lot.unit_quantity
    1.0
    >>> lot.quantity
    1.0
