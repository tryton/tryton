==================================
Stock Location Move Empty Scenario
==================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> yesterday = today - datetime.timedelta(1)
    >>> tomorrow = today + datetime.timedelta(1)

Activate modules::

    >>> config = activate_modules('stock_location_move')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> storage1 = Location(name="Storage 1", parent=storage_loc)
    >>> storage1.save()
    >>> pallet1 = Location(name="Pallet 1", parent=storage_loc, movable=True)
    >>> pallet1.save()
    >>> pallet2 = Location(name="Pallet 2", parent=storage_loc, movable=True)
    >>> pallet2.save()
    >>> pallet3 = Location(name="Pallet 3", parent=storage_loc, movable=True)
    >>> pallet3.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(0)
    >>> template.save()
    >>> product1 = Product()
    >>> product1.template = template
    >>> product1.save()
    >>> product2 = Product()
    >>> product2.template = template
    >>> product2.save()
    >>> product3 = Product()
    >>> product3.template = template
    >>> product3.save()

Fill storage locations::

    >>> StockMove = Model.get('stock.move')

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product1
    >>> incoming_move.quantity = 1
    >>> incoming_move.unit_price = Decimal('0')
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage1
    >>> incoming_move.effective_date = yesterday
    >>> incoming_move.click('do')

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product2
    >>> incoming_move.quantity = 1
    >>> incoming_move.unit_price = Decimal('0')
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = pallet1
    >>> incoming_move.effective_date = yesterday
    >>> incoming_move.click('do')

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product3
    >>> incoming_move.quantity = 2
    >>> incoming_move.unit_price = Decimal('0')
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = pallet2
    >>> incoming_move.effective_date = yesterday
    >>> incoming_move.click('do')

Ship 1 product from the locations::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer
    >>> shipment.warehouse = warehouse_loc
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('0')
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product2
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('0')
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product3
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('0')
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')

Check empty non movable location are still active::

    >>> storage1.reload()
    >>> bool(storage1.active)
    True

Check empty location are deactivated::

    >>> pallet1.reload()
    >>> bool(pallet1.active)
    False

Check non empty location are still active::

    >>> pallet2.reload()
    >>> bool(pallet2.active)
    True

Check non changed empty location are still active::

    >>> pallet3.reload()
    >>> bool(pallet3.active)
    True
