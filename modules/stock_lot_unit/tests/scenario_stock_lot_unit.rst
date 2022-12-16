=======================
Stock Lot Unit Scenario
=======================

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

    >>> config = activate_modules('stock_lot_unit')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create supplier::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.lot_unit = unit
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create an incoming shipment without lot::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move1 = shipment.incoming_moves.new()
    >>> move1.product = product
    >>> move1.quantity = 60
    >>> move1.unit_price = Decimal('8')
    >>> move1.from_location = supplier_loc
    >>> move1.to_location = input_loc
    >>> move2 = shipment.incoming_moves.new()
    >>> move2.product = product
    >>> move2.quantity = 40
    >>> move2.unit_price = Decimal('8')
    >>> move2.from_location = supplier_loc
    >>> move2.to_location = input_loc
    >>> shipment.click('receive')
    >>> shipment.click('done')

Let's ship a product with a lot::

    >>> Lot = Model.get('stock.lot')
    >>> lot = Lot(number='00001', product=product)
    >>> lot.unit == unit
    True
    >>> lot.unit_quantity
    1.0
    >>> lot.save()

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('20')
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.lot = lot
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')

Let's ship now two times the same lot::

    >>> lot = Lot(number='00002', product=product)
    >>> lot.save()

    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer
    >>> move1 = shipment.outgoing_moves.new()
    >>> move1.product = product
    >>> move1.quantity = 1
    >>> move1.unit_price = Decimal('20')
    >>> move1.from_location = output_loc
    >>> move1.to_location = customer_loc
    >>> move1.lot = lot
    >>> move2 = shipment.outgoing_moves.new()
    >>> move2.product = product
    >>> move2.quantity = 1
    >>> move2.unit_price = Decimal('20')
    >>> move2.from_location = output_loc
    >>> move2.to_location = customer_loc
    >>> move2.lot = lot
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    LotUnitQuantityError: ...

Now let's ship one move with a quantity bigger than lot unit quantity::

    >>> lot = Lot(number='00003', product=product)
    >>> lot.unit_quantity = 3
    >>> lot.save()

    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 4
    >>> move.unit_price = Decimal('20')
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.lot = lot
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    LotUnitQuantityError: ...

Make an inventory::

    >>> lot = Lot(number='00004', product=product)
    >>> lot.unit_quantity = 2
    >>> lot.save()

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> line = inventory.lines.new()
    >>> line.product = product
    >>> line.lot = lot
    >>> line.quantity = 3
    >>> inventory.save()
    >>> inventory.click('confirm')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    LotUnitQuantityError: ...

    >>> line, = inventory.lines
    >>> line.quantity = 2
    >>> inventory.click('confirm')
