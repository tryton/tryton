===========================
Stock Shipment Out Scenario
===========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([('name', '=', 'stock')])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.save()
    >>> product.template = template
    >>> product.save()

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
    >>> shipment_out.company = company

Add two shipment lines of same product::

    >>> StockMove = Model.get('stock.move')
    >>> shipment_out.outgoing_moves.extend([StockMove(), StockMove()])
    >>> for move in shipment_out.outgoing_moves:
    ...     move.product = product
    ...     move.uom =unit
    ...     move.quantity = 1
    ...     move.from_location = output_loc
    ...     move.to_location = customer_loc
    ...     move.company = company
    ...     move.unit_price = Decimal('1')
    ...     move.currency = company.currency
    >>> shipment_out.save()

Set the shipment state to waiting::

    >>> shipment_out.click('wait')
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    2

Make 1 unit of the product available::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('1')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Assign the shipment now::

    >>> shipment_out.click('assign_try')
    False
    >>> shipment_out.reload()
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    2
    >>> states = [m.state for m in shipment_out.inventory_moves]
    >>> states.sort()
    >>> states
    [u'assigned', u'draft']
    >>> effective_dates = [m.effective_date for m in
    ...     shipment_out.inventory_moves]
    >>> len(set(effective_dates))
    2
    >>> planned_dates = [m.planned_date for m in
    ...     shipment_out.outgoing_moves]
    >>> len(set(planned_dates))
    1

Delete the draft move, assign and pack shipment::

    >>> for move in shipment_out.inventory_moves:
    ...     if move.state == 'draft':
    ...         break
    >>> shipment_out.inventory_moves.remove(move)
    >>> shipment_out.click('assign_try')
    True
    >>> shipment_out.click('pack')
    >>> all(m.state == 'assigned' for m in shipment_out.outgoing_moves)
    True
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    1
    >>> shipment_out.inventory_moves[0].state
    u'done'
    >>> sum([m.quantity for m in shipment_out.inventory_moves]) == \
    ...     sum([m.quantity for m in shipment_out.outgoing_moves])
    True

Set the state as Done::

    >>> shipment_out.click('done')
    >>> all(m.state == 'done' for m in shipment_out.outgoing_moves)
    True
    >>> planned_dates = [m.planned_date for m in
    ...     shipment_out.outgoing_moves]
    >>> planned_dates == [today, today]
    True
    >>> effective_dates = [m.effective_date for m in
    ...     shipment_out.outgoing_moves]
    >>> len(set(effective_dates))
    1
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    1
    >>> shipment_out.inventory_moves[0].state
    u'done'
    >>> sum([m.quantity for m in shipment_out.inventory_moves]) == \
    ...     sum([m.quantity for m in shipment_out.outgoing_moves])
    True

Create Shipment Out with effective date::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = yesterday
    >>> shipment_out.effective_date = yesterday
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> shipment_out.company = company
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom =unit
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_out.click('wait')

Make 1 unit of the product available::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = yesterday
    >>> incoming_move.effective_date = yesterday
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('1')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Finish the shipment::

    >>> shipment_out.click('assign_try')
    True
    >>> shipment_out.click('pack')
    >>> shipment_out.click('done')
    >>> shipment_out.state
    u'done'
    >>> outgoing_move, = shipment_out.outgoing_moves
    >>> outgoing_move.effective_date == yesterday
    True
    >>> inventory_move, = shipment_out.inventory_moves
    >>> inventory_move.effective_date == yesterday
    True

