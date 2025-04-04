=========================================
Stock Product Locations Template Scenario
=========================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('stock_product_location', create_company)

Get currency::

    >>> currency = get_currency()

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
    >>> template_location = template.locations.new()
    >>> template_location.warehouse = warehouse_loc
    >>> template_location.location = child_loc
    >>> template.save()
    >>> product, = template.products

Create Shipment in::

    >>> Shipmentin = Model.get('stock.shipment.in')
    >>> shipment_in = Shipmentin()
    >>> shipment_in.planned_date = today
    >>> shipment_in.supplier = supplier
    >>> shipment_in.warehouse = warehouse_loc

Add one shipment line of product::

    >>> move = shipment_in.incoming_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = currency
    >>> shipment_in.save()

Test that to_location is child location on reception::

    >>> shipment_in.click('receive')
    >>> move, = shipment_in.inventory_moves
    >>> assertEqual(move.to_location, child_loc)

Create return shipment out::

    >>> Shipment_out_Return = Model.get('stock.shipment.out.return')
    >>> shipment_out_return = Shipment_out_Return()
    >>> shipment_out_return.customer = customer
    >>> shipment_out_return.save()

Add one shipment return line::

    >>> move = shipment_out_return.incoming_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = customer_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = currency
    >>> shipment_out_return.save()

Test that to_location is child location on reception::

    >>> shipment_out_return.click('receive')
    >>> move, = shipment_out_return.inventory_moves
    >>> assertEqual(move.to_location, child_loc)
