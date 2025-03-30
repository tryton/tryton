===========================
Stock Shipment Out Scenario
===========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import (
    ...     activate_modules, assertEqual, assertNotEqual, set_user)

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')
    >>> User = Model.get('res.user')

Set employee::

    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> user = User(config.user)
    >>> user.employees.append(employee)
    >>> user.employee = employee
    >>> user.save()
    >>> set_user(user.id)

Get currency::

    >>> currency = get_currency()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
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
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc

Add two shipment lines of same product::

    >>> StockMove = Model.get('stock.move')
    >>> shipment_out.outgoing_moves.extend([StockMove(), StockMove()])
    >>> for move in shipment_out.outgoing_moves:
    ...     move.product = product
    ...     move.unit = unit
    ...     move.quantity = 1
    ...     move.from_location = output_loc
    ...     move.to_location = customer_loc
    ...     move.unit_price = Decimal('1')
    ...     move.currency = currency
    >>> shipment_out.save()
    >>> shipment_out.number
    >>> shipment_out.picked_by
    >>> shipment_out.packed_by
    >>> shipment_out.shipped_by
    >>> shipment_out.done_by

Set the shipment state to waiting::

    >>> shipment_out.click('wait')
    >>> shipment_out.state
    'waiting'
    >>> assertNotEqual(shipment_out.number, None)
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    2
    >>> assertEqual(
    ...     {m.origin for m in shipment_out.inventory_moves},
    ...     {m for m in shipment_out.outgoing_moves})

Make 1 unit of the product available::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.unit = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.unit_price = Decimal('1')
    >>> incoming_move.currency = currency
    >>> incoming_move.click('do')

Assign the shipment now::

    >>> shipment_assign = shipment_out.click('assign_wizard')
    >>> len(shipment_assign.form.moves)
    1
    >>> shipment_assign.execute('end')
    >>> shipment_out.reload()
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    2
    >>> states = [m.state for m in shipment_out.inventory_moves]
    >>> states.sort()
    >>> states
    ['assigned', 'draft']
    >>> effective_dates = [m.effective_date for m in
    ...     shipment_out.inventory_moves]
    >>> len(set(effective_dates))
    1
    >>> planned_dates = [m.planned_date for m in
    ...     shipment_out.outgoing_moves]
    >>> len(set(planned_dates))
    1

Ignore non assigned moves and pack shipment::

    >>> shipment_assign = shipment_out.click('assign_wizard')
    >>> shipment_assign.execute('ignore')
    >>> sorted([m.quantity for m in shipment_out.inventory_moves])
    [0.0, 1.0]
    >>> shipment_out.picked_by
    >>> shipment_out.packed_by
    >>> shipment_out.shipped_by
    >>> shipment_out.done_by

    >>> picking_list = Report('stock.shipment.out.picking_list')
    >>> _ = picking_list.execute([shipment_out])

    >>> shipment_out.click('pick')
    >>> assertEqual(shipment_out.picked_by, employee)
    >>> shipment_out.packed_by
    >>> shipment_out.shipped_by
    >>> shipment_out.done_by

    >>> shipment_out.click('pack')
    >>> assertEqual(shipment_out.packed_by, employee)
    >>> shipment_out.shipped_by
    >>> shipment_out.done_by
    >>> [m.state for m in shipment_out.outgoing_moves]
    ['assigned']
    >>> len(shipment_out.inventory_moves)
    1
    >>> shipment_out.inventory_moves[0].state
    'done'
    >>> assertEqual(sum([m.quantity for m in shipment_out.inventory_moves]),
    ...     sum([m.quantity for m in shipment_out.outgoing_moves]))

    >>> delivery_note = Report('stock.shipment.out.delivery_note')
    >>> _ = delivery_note.execute([shipment_out])

Set the state as Shipped::

    >>> shipment_out.click('ship')
    >>> assertEqual(shipment_out.shipped_by, employee)
    >>> shipment_out.done_by

Set the state as Done::

    >>> shipment_out.click('do')
    >>> assertEqual(shipment_out.done_by, employee)
    >>> [m.state for m in shipment_out.outgoing_moves]
    ['done']
    >>> planned_dates = [m.planned_date for m in
    ...     shipment_out.outgoing_moves]
    >>> assertEqual(planned_dates, [today])
    >>> effective_dates = [m.effective_date for m in
    ...     shipment_out.outgoing_moves]
    >>> len(set(effective_dates))
    1
    >>> len(shipment_out.outgoing_moves)
    1
    >>> len(shipment_out.inventory_moves)
    1
    >>> shipment_out.inventory_moves[0].state
    'done'
    >>> assertEqual(sum([m.quantity for m in shipment_out.inventory_moves]),
    ...     sum([m.quantity for m in shipment_out.outgoing_moves]))

Create Shipment Out with effective date::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = yesterday
    >>> shipment_out.effective_date = yesterday
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = currency
    >>> shipment_out.click('wait')

Make 1 unit of the product available::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.unit = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = yesterday
    >>> incoming_move.effective_date = yesterday
    >>> incoming_move.unit_price = Decimal('1')
    >>> incoming_move.currency = currency
    >>> incoming_move.click('do')

Finish the shipment::

    >>> shipment_out.click('assign_try')
    >>> shipment_out.click('pick')
    >>> len(shipment_out.inventory_moves)
    1
    >>> len(shipment_out.outgoing_moves)
    1
    >>> shipment_out.click('pack')
    >>> shipment_out.click('pick')
    >>> len(shipment_out.inventory_moves)
    1
    >>> len(shipment_out.outgoing_moves)
    1
    >>> shipment_out.click('pack')

Finish the shipment::

    >>> shipment_out.click('do')
    >>> shipment_out.state
    'done'
    >>> outgoing_move, = shipment_out.outgoing_moves
    >>> assertEqual(outgoing_move.effective_date, yesterday)
    >>> inventory_move, = shipment_out.inventory_moves
    >>> assertEqual(inventory_move.effective_date, yesterday)

Reschedule shipment::

    >>> shipment_copy, = shipment_out.duplicate()
    >>> shipment_copy.planned_date = yesterday
    >>> shipment_copy.click('wait')
    >>> Cron = Model.get('ir.cron')
    >>> cron = Cron(method='stock.shipment.out|reschedule')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'months'
    >>> cron.click('run_once')
    >>> shipment_copy.reload()
    >>> assertEqual(shipment_copy.planned_date, today)
