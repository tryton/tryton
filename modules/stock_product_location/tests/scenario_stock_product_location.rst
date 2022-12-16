================================
Stock Product Locations Scenario
================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock_product_location')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create supplier::

    >>> supplier = Party(name='Suppier')
    >>> supplier.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])

Create new location::

    >>> Location = Model.get('stock.location')
    >>> child_loc = Location()
    >>> child_loc.name = 'Child Location'
    >>> child_loc.parent = storage_loc
    >>> child_loc.code = 'CHI'
    >>> child_loc.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products
    >>> product_location = product.locations.new()
    >>> product_location.warehouse = warehouse_loc
    >>> product_location.location = child_loc
    >>> product.save()

Create Shipment in::

    >>> Shipmentin = Model.get('stock.shipment.in')
    >>> shipment_in = Shipmentin()
    >>> shipment_in.planned_date = today
    >>> shipment_in.supplier = supplier
    >>> shipment_in.warehouse = warehouse_loc
    >>> shipment_in.company = company

Add one shipment line of product::

    >>> move = shipment_in.incoming_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_in.save()

Test that to_location is child location on reception::

    >>> shipment_in.click('receive')
    >>> move, = shipment_in.inventory_moves
    >>> move.to_location == child_loc
    True

Create return shipment out::

    >>> Shipment_out_Return = Model.get('stock.shipment.out.return')
    >>> shipment_out_return = Shipment_out_Return()
    >>> shipment_out_return.customer = customer
    >>> shipment_out_return.save()

Add one shipment return line::

    >>> move = shipment_out_return.incoming_moves.new()
    >>> move.product = product
    >>> move.uom =unit
    >>> move.quantity = 1
    >>> move.from_location = customer_loc
    >>> move.to_location =  input_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_out_return.save()

Test that to_location is child location on reception::

    >>> shipment_out_return.click('receive')
    >>> move, = shipment_out_return.inventory_moves
    >>> move.to_location == child_loc
    True
