=============================================
Stock Shipment Internal with Transit Scenario
=============================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock')

    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Shipment = Model.get('stock.shipment.internal')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse1, = Location.find([('type', '=', 'warehouse')])
    >>> warehouse2, = warehouse1.duplicate()

Add lead time between warehouses::

    >>> LeadTime = Model.get('stock.location.lead_time')
    >>> lead_time = LeadTime()
    >>> lead_time.warehouse_from = warehouse1
    >>> lead_time.warehouse_to = warehouse2
    >>> lead_time.lead_time = dt.timedelta(1)
    >>> lead_time.save()

Create Internal Shipment with lead time::

    >>> shipment = Shipment()
    >>> shipment.planned_date = tomorrow
    >>> shipment.from_location = warehouse1.storage_location
    >>> shipment.to_location = warehouse2.storage_location
    >>> bool(shipment.transit_location)
    True
    >>> shipment.planned_start_date == today
    True
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 2
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> shipment.click('wait')
    >>> len(shipment.moves)
    2
    >>> outgoing_move, = shipment.outgoing_moves
    >>> outgoing_move.quantity
    2.0
    >>> outgoing_move.from_location == shipment.from_location
    True
    >>> outgoing_move.to_location == shipment.transit_location
    True
    >>> outgoing_move.planned_date == today
    True
    >>> incoming_move, = shipment.incoming_moves
    >>> incoming_move.quantity
    2.0
    >>> incoming_move.from_location == shipment.transit_location
    True
    >>> incoming_move.to_location == shipment.to_location
    True
    >>> incoming_move.planned_date == tomorrow
    True

    >>> outgoing_move.quantity = 1
    >>> outgoing_move.save()

    >>> shipment.click('assign_force')
    >>> shipment.effective_start_date = yesterday
    >>> shipment.click('ship')
    >>> incoming_move, = shipment.incoming_moves
    >>> incoming_move.quantity
    1.0
    >>> shipment.outgoing_moves[0].state
    'done'
    >>> shipment.outgoing_moves[0].effective_date == yesterday
    True
    >>> shipment.click('done')
    >>> shipment.incoming_moves[0].state
    'done'
    >>> shipment.incoming_moves[0].effective_date == today
    True
