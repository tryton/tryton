==============================
Stock Lot Shipment In Scenario
==============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_lot', create_company)

    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentIn = Model.get('stock.shipment.in')

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

Set 2 lots::

    >>> lot1 = Lot(number="1", product=product)
    >>> lot1.save()
    >>> lot2 = Lot(number="2", product=product)
    >>> lot2.save()

Create a shipment::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('5')
    >>> move.currency = shipment.company.currency
    >>> shipment.save()

Receive the shipment with one lot::

    >>> incoming_move, = shipment.incoming_moves
    >>> incoming_move.lot = lot1
    >>> shipment.click('receive')
    >>> shipment.state
    'received'

Change lot and try to finish::

    >>> incoming_move, = shipment.inventory_moves
    >>> assertEqual(incoming_move.lot, lot1)
    >>> incoming_move.lot = lot2
    >>> shipment.click('do')
    Traceback (most recent call last):
        ...
    ShipmentCheckQuantityWarning: ...
    >>> incoming_move.reload()
    >>> incoming_move.lot = lot1
    >>> incoming_move.save()

Finish the shipment::

    >>> shipment.click('do')
    >>> shipment.state
    'done'
