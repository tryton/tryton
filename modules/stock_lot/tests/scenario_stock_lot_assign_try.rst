=================================
Stock Lot Assign Request Scenario
=================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal

    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock_lot')
    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentOut = Model.get('stock.shipment.out')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

Create lot::

    >>> lot = Lot()
    >>> lot.number = 'LOT'
    >>> lot.product = product
    >>> lot.save()

Get stock locations::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> zone1 = Location(name='Zone1')
    >>> zone1.parent = storage_loc
    >>> zone1.type = 'storage'
    >>> zone1.save()
    >>> zone2, = zone1.duplicate(default={'name': 'Zone2'})

Add product quantities on zones storage locations::

    >>> inventory = Inventory()
    >>> inventory.location = zone1
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'
    >>> inventory = Inventory()
    >>> inventory.location = zone2
    >>> inventory_line = inventory.lines.new()
    >>> inventory_line.product = product
    >>> inventory_line.lot = lot
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Create shipment out::

    >>> shipment = ShipmentOut()
    >>> shipment.planned_date = today
    >>> shipment.customer = customer
    >>> shipment.warehouse = warehouse_loc
    >>> shipment.company = company
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 10
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment.click('wait')

Request specific lot in stock assignation::

    >>> move, = shipment.inventory_moves
    >>> move.lot = lot
    >>> move.save()

Assign the shipment::

    >>> shipment.click('assign_try')
    True
    >>> shipment.state
    'assigned'
    >>> move, = shipment.inventory_moves
    >>> move.from_location.name
    'Zone2'
