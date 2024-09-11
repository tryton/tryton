===================================================
Stock Shipment Out Same Storage and Output Scenario
===================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Move = Model.get('stock.move')

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
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> warehouse_loc.output_location = storage_loc
    >>> warehouse_loc.save()

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('5')
    >>> move.currency = get_currency()
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> shipment_out.save()

    >>> len(shipment_out.outgoing_moves)
    1
    >>> len(shipment_out.inventory_moves)
    0

Set the shipment state to waiting::

    >>> shipment_out.click('wait')
    >>> shipment_out.state
    'waiting'
    >>> len(shipment_out.outgoing_moves)
    1
    >>> len(shipment_out.inventory_moves)
    0

Try to assign::

    >>> shipment_out.click('assign_try')
    >>> shipment_out.state
    'waiting'
    >>> move, = shipment_out.outgoing_moves
    >>> move.state
    'draft'

Fill storage location::

    >>> move = Move()
    >>> move.from_location = warehouse_loc.lost_found_location
    >>> move.to_location = storage_loc
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.click('do')
    >>> move.state
    'done'

Try to assign again::

    >>> shipment_out.click('assign_try')
    >>> shipment_out.state
    'assigned'
    >>> move, = shipment_out.outgoing_moves
    >>> move.state
    'assigned'

Pack the shipment::

    >>> shipment_out.click('pack')
    >>> shipment_out.state
    'packed'
    >>> len(shipment_out.outgoing_moves)
    1
    >>> len(shipment_out.inventory_moves)
    0
