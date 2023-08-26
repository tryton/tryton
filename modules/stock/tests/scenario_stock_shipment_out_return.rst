==================================
Stock Shipment Out Return Scenario
==================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('stock')

    >>> Party = Model.get('party.party')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

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
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create Shipment Out Return::

    >>> ShipmentOutReturn = Model.get('stock.shipment.out.return')
    >>> shipment = ShipmentOutReturn()
    >>> shipment.customer = customer
    >>> shipment.warehouse = warehouse_loc
    >>> shipment.company = company
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = customer_loc
    >>> move.to_location = warehouse_loc.input_location
    >>> move.unit_price = Decimal('20')
    >>> move.currency = company.currency
    >>> shipment.save()

    >>> len(shipment.incoming_moves)
    1
    >>> len(shipment.inventory_moves)
    0

Receive shipment::

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

    >>> restocking_list = Report('stock.shipment.out.return.restocking_list')
    >>> _ = restocking_list.execute([shipment])

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
