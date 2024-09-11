========================================
Stock Internal Supply Lead Time Scenario
========================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock_supply', create_company)

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

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
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Create second warehouse::

    >>> sec_warehouse_loc, = warehouse_loc.duplicate()

Add lead time between warehouses::

    >>> LeadTime = Model.get('stock.location.lead_time')
    >>> lead_time = LeadTime()
    >>> lead_time.warehouse_from = warehouse_loc
    >>> lead_time.warehouse_to = sec_warehouse_loc
    >>> lead_time.lead_time = dt.timedelta(1)
    >>> lead_time.save()

Create internal order point::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.product = product
    >>> order_point.location = sec_warehouse_loc.storage_location
    >>> order_point.provisioning_location = warehouse_loc.storage_location
    >>> order_point.type = 'internal'
    >>> order_point.min_quantity = 10
    >>> order_point.target_quantity = 15
    >>> order_point.save()

Create inventory to add enough quantity in first warehouse::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = warehouse_loc.storage_location
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Create needs for tomorrow in second warehouse::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment = ShipmentOut()
    >>> shipment.planned_date = tomorrow
    >>> shipment.customer = customer
    >>> shipment.warehouse = sec_warehouse_loc
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = sec_warehouse_loc.output_location
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20')
    >>> move.currency = get_currency()
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'

Execute internal supply::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> Wizard('stock.supply').execute('create_')
    >>> shipments = ShipmentInternal.find([], order=[('planned_date', 'ASC')])
    >>> len(shipments)
    2
    >>> first, second = shipments

    >>> assertEqual(first.planned_date, today)
    >>> first.state
    'request'
    >>> len(first.moves)
    1
    >>> move, = first.moves
    >>> assertEqual(move.from_location, warehouse_loc.storage_location)
    >>> assertEqual(move.to_location, sec_warehouse_loc.storage_location)
    >>> move.quantity
    15.0

    >>> assertEqual(second.planned_date, tomorrow)
    >>> second.state
    'request'
    >>> len(second.moves)
    1
    >>> move, = second.moves
    >>> assertEqual(move.from_location, warehouse_loc.storage_location)
    >>> assertEqual(move.to_location, sec_warehouse_loc.storage_location)
    >>> move.quantity
    10.0
