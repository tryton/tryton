============================
Stock Assign Manual Scenario
============================

Imports::

    >>> import datetime as dt
    >>> import json
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> today = dt.date.today()

Activate stock_assign_manual::

    >>> config = activate_modules('stock_assign_manual')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> storage_loc2, = storage_loc.duplicate(
    ...     default={'parent': storage_loc.id})

Fill locations::

    >>> StockMove = Model.get('stock.move')
    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('5')
    >>> move.currency = company.currency
    >>> move.click('do')

    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 4
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc2
    >>> move.unit_price = Decimal('5')
    >>> move.currency = company.currency
    >>> move.click('do')

Make a customer shipment::

    >>> Shipment = Model.get('stock.shipment.out')
    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 2
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20')
    >>> move.currency = company.currency
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 3
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'

Assign manually the first move::

    >>> assign_manual = Wizard('stock.shipment.assign.manual', [shipment])
    >>> assign_manual.form.move == shipment.inventory_moves[0]
    True
    >>> assign_manual.form.move_quantity
    2.0
    >>> assign_manual.form.place = json.dumps([storage_loc.id, product.id])
    >>> assign_manual.execute('assign')
    >>> assign_manual.form.move_quantity
    1.0
    >>> assign_manual.form.place = json.dumps([storage_loc2.id, product.id])
    >>> assign_manual.execute('assign')
    >>> assign_manual.form.move_quantity
    3.0
    >>> assign_manual.execute('skip')
    >>> assign_manual.state
    'end'

Shipment is not yet assigned::

    >>> shipment.state
    'waiting'
    >>> sorted([m.state for m in shipment.inventory_moves])
    ['assigned', 'assigned', 'draft']
    >>> [m.quantity for m in shipment.inventory_moves if m.state == 'assigned']
    [1.0, 1.0]
    >>> [m.from_location for m in shipment.inventory_moves
    ...     if m.state == 'assigned'] == [storage_loc, storage_loc2]
    True

Assign manually remaining move::

    >>> assign_manual = Wizard('stock.shipment.assign.manual', [shipment])
    >>> assign_manual.form.place = json.dumps([storage_loc2.id, product.id])
    >>> assign_manual.execute('assign')

    >>> shipment.state
    'assigned'

Unassign move::

    >>> AssignedMove = Model.get('stock.shipment.assigned.move')
    >>> sorted([m.state for m in shipment.inventory_moves])
    ['assigned', 'assigned', 'assigned']
    >>> move1, _, _ = shipment.inventory_moves
    >>> unassign_manual = Wizard('stock.shipment.unassign.manual', [shipment])
    >>> move_to_unassign = AssignedMove()
    >>> move_to_unassign.move = StockMove(move1.id)
    >>> move_to_unassign.unassigned_quantity = 1.0
    >>> unassign_manual.form.moves.append(move_to_unassign)
    >>> unassign_manual.execute('unassign')
    >>> shipment.state
    'waiting'
    >>> sorted([(m.state, m.quantity) for m in shipment.inventory_moves])
    [('assigned', 1.0), ('assigned', 3.0), ('draft', 1.0)]

Unassign a second move to be merged::

    >>> move2, = [i for i in shipment.inventory_moves if (
    ...     i.quantity == 1.0 and i.state == 'assigned')]
    >>> unassign_manual = Wizard('stock.shipment.unassign.manual', [shipment])
    >>> move_to_unassign = AssignedMove()
    >>> move_to_unassign.move = StockMove(move2.id)
    >>> move_to_unassign.unassigned_quantity = 1.0
    >>> unassign_manual.form.moves.append(move_to_unassign)
    >>> unassign_manual.execute('unassign')
    >>> shipment.state
    'waiting'
    >>> sorted([(m.state, m.quantity) for m in shipment.inventory_moves])
    [('assigned', 3.0), ('draft', 2.0)]

Unassign partially third move::

    >>> move3, = [i for i in shipment.inventory_moves
    ...     if i.quantity == 3.0 and i.state == 'assigned']
    >>> unassign_manual = Wizard('stock.shipment.unassign.manual', [shipment])
    >>> move_to_unassign = AssignedMove()
    >>> move_to_unassign.move = StockMove(move3.id)
    >>> move_to_unassign.unassigned_quantity = 2.0
    >>> unassign_manual.form.moves.append(move_to_unassign)
    >>> unassign_manual.execute('unassign')
    >>> shipment.state
    'waiting'
    >>> sorted([(m.state, m.quantity) for m in shipment.inventory_moves])
    [('assigned', 1.0), ('draft', 2.0), ('draft', 2.0)]
