==========================
Stock Shipment In Scenario
==========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('stock')

    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentIn = Model.get('stock.shipment.in')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create supplier::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create a shipment::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('5')
    >>> move.currency = company.currency
    >>> shipment.save()

    >>> len(shipment.incoming_moves)
    1
    >>> len(shipment.inventory_moves)
    0

Receive the shipment::

    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> len(shipment.incoming_moves)
    1
    >>> all(m.state == 'done' for m in shipment.incoming_moves)
    True
    >>> len(shipment.inventory_moves)
    1
    >>> all(m.state == 'draft' for m in shipment.inventory_moves)
    True

    >>> restocking_list = Report('stock.shipment.in.restocking_list')
    >>> _ = restocking_list.execute([shipment])

Change inventory quantity and try to finish::

    >>> inventory_move, = shipment.inventory_moves
    >>> inventory_move.quantity = 11
    >>> shipment.click('done')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    ShipmentCheckQuantityWarning: ...
    >>> inventory_move.reload()
    >>> inventory_move.quantity = 10
    >>> inventory_move.save()

Add extra product to inventory and try to finish::

    >>> product2, = product.duplicate()

    >>> move = shipment.inventory_moves.new()
    >>> move.product = product2
    >>> move.quantity = 1
    >>> move.from_location = input_loc
    >>> move.to_location = storage_loc
    >>> shipment.click('done')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    ShipmentCheckQuantityWarning: ...
    >>> move = shipment.inventory_moves[-1]
    >>> shipment.inventory_moves.remove(move)
    >>> shipment.save()

Finish the shipment::

    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> len(shipment.incoming_moves)
    1
    >>> len(shipment.inventory_moves)
    1
    >>> all(m.state == 'done' for m in shipment.inventory_moves)
    True
