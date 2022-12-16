===============================
Stock Lot Shipment Out Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock_lot')

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
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.lot_required = ['storage']
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
    >>> shipment_out.company = company
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom =unit
    >>> move.quantity = 10
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_out.save()

Set the shipment state to waiting::

    >>> shipment_out.click('wait')
    >>> len(shipment_out.outgoing_moves)
    1
    >>> len(shipment_out.inventory_moves)
    1

Split inventory move::

    >>> move, = shipment_out.inventory_moves
    >>> move.quantity = 7
    >>> move.save()
    >>> with config.set_context(_stock_move_split=True):
    ...     _ = move.duplicate(default=dict(quantity=3))
    >>> shipment_out.reload()

Assign the shipment::

    >>> shipment_out.click('assign_force')
    >>> shipment_out.state
    'assigned'
    >>> len(shipment_out.outgoing_moves)
    1

Try to pick without lot::

    >>> shipment_out.click('pick')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    RequiredValidationError: ...

Set 2 lots::

    >>> Lot = Model.get('stock.lot')
    >>> for i, move in enumerate(shipment_out.inventory_moves, start=1):
    ...     lot = Lot(number='%05i' % i, product=move.product)
    ...     lot.save()
    ...     move.lot = lot
    >>> shipment_out.save()

Pick the shipment::

    >>> shipment_out.click('pick')
    >>> shipment_out.state
    'picked'
    >>> len(shipment_out.outgoing_moves)
    3
    >>> sorted([m.quantity for m in shipment_out.outgoing_moves])
    [0.0, 3.0, 7.0]
    >>> lot_quantities = {}
    >>> for move in shipment_out.outgoing_moves:
    ...     number = move.lot.number if move.lot else ''
    ...     quantity = lot_quantities.setdefault(number, 0)
    ...     lot_quantities[number] += move.quantity
    >>> sorted(lot_quantities.items())
    [('', 0.0), ('00001', 3.0), ('00002', 7.0)]
