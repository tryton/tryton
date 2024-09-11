=========================================================
Stock Shipment Out Return Same Storage and Input Scenario
=========================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock', create_company)

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
    >>> storage1 = Location(name="Storage 1", parent=storage_loc)
    >>> storage1.save()

Use storage location as input location::

    >>> warehouse_loc.input_location = storage_loc
    >>> warehouse_loc.save()

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
    >>> move.to_location = storage1
    >>> move.unit_price = Decimal('20')
    >>> move.currency = get_currency()
    >>> shipment.save()

    >>> len(shipment.incoming_moves)
    1
    >>> len(shipment.inventory_moves)
    0

Shipment is done when receiving::

    >>> shipment.click('receive')
    >>> shipment.state
    'done'
    >>> move, = shipment.incoming_moves
    >>> move.state
    'done'
    >>> len(shipment.inventory_moves)
    0
