====================================
Stock Lot Shipment Internal Scenario
====================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertTrue

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock_lot', create_company)

    >>> LeadTime = Model.get('stock.location.lead_time')
    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Shipment = Model.get('stock.shipment.internal')

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

    >>> warehouse1, = Location.find([('type', '=', 'warehouse')])
    >>> warehouse2, = warehouse1.duplicate()

Add lead time between warehouses::

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
    >>> assertTrue(shipment.transit_location)
    >>> assertEqual(shipment.planned_start_date, today)
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 3
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> shipment.save()

Set the shipment state to waiting::


    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> len(shipment.outgoing_moves)
    1
    >>> len(shipment.incoming_moves)
    1

Split outgoing moves::

    >>> move, = shipment.outgoing_moves
    >>> move.quantity = 1
    >>> move.save()
    >>> with config.set_context(_stock_move_split=True):
    ...     _ = move.duplicate(default=dict(quantity=2))
    >>> shipment.reload()

Assign the shipment::

    >>> shipment.click('assign_force')
    >>> shipment.state
    'assigned'

    >>> len(shipment.incoming_moves)
    1

Check the inventory moves origin::

    >>> incoming_move, = shipment.incoming_moves
    >>> for move in shipment.outgoing_moves:
    ...     assertEqual(move.origin, incoming_move)

Set 2 lots::

    >>> for i, move in enumerate(shipment.outgoing_moves, start=1):
    ...     lot = Lot(number='%05i' % i, product=move.product)
    ...     lot.save()
    ...     move.lot = lot
    >>> shipment.save()

Ship the shipment::

    >>> shipment.effective_start_date = yesterday
    >>> shipment.click('pack')
    >>> shipment.click('ship')
    >>> shipment.state
    'shipped'
    >>> len(shipment.incoming_moves)
    3
    >>> sorted([m.quantity for m in shipment.incoming_moves])
    [0.0, 1.0, 2.0]
    >>> lot_quantities = {}
    >>> for move in shipment.incoming_moves:
    ...     number = move.lot.number if move.lot else ''
    ...     quantity = lot_quantities.setdefault(number, 0)
    ...     lot_quantities[number] += move.quantity
    >>> sorted(lot_quantities.items())
    [('', 0.0), ('00001', 1.0), ('00002', 2.0)]

Check the outgoing moves have an incoming move origin with the same lot::

    >>> for move in shipment.outgoing_moves:
    ...     assertEqual(move.lot, move.origin.lot)
