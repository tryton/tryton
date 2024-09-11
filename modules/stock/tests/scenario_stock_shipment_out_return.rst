==================================
Stock Shipment Out Return Scenario
==================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertNotEqual

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Party = Model.get('party.party')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')

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
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = customer_loc
    >>> move.to_location = warehouse_loc.input_location
    >>> move.unit_price = Decimal('20')
    >>> move.currency = get_currency()
    >>> shipment.save()
    >>> assertNotEqual(shipment.number, None)

    >>> len(shipment.incoming_moves)
    1
    >>> len(shipment.inventory_moves)
    0

Receive shipment::

    >>> shipment.click('receive')
    >>> shipment.state
    'received'

    >>> [m.state for m in shipment.incoming_moves]
    ['done']
    >>> [m.state for m in shipment.inventory_moves]
    ['draft']

    >>> restocking_list = Report('stock.shipment.out.return.restocking_list')
    >>> _ = restocking_list.execute([shipment])

Finish the shipment::

    >>> shipment.click('do')
    >>> shipment.state
    'done'
    >>> len(shipment.incoming_moves)
    1
    >>> [m.state for m in shipment.inventory_moves]
    ['done']
