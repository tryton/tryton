=================================
Stock Shipment Reporting Scenario
=================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock', create_company)

Get currency::

    >>> currency = get_currency()

Create customer & supplier::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

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
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Create Shipment In::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment_in = ShipmentIn()
    >>> shipment_in.planned_date = today
    >>> shipment_in.supplier = supplier
    >>> shipment_in.warehouse = warehouse_loc

Receive a bunch of products::

    >>> move = shipment_in.incoming_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 100
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = currency
    >>> shipment_in.save()
    >>> shipment_in.click('receive')
    >>> shipment_in.click('do')

Testing the report::

    >>> supplier_restocking_list = Report('stock.shipment.in.restocking_list')
    >>> ext, _, _, name = supplier_restocking_list.execute([shipment_in], {})
    >>> ext
    'odt'
    >>> name
    'Restocking List-1'

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc

Add two shipment lines of same product and go through the workflow::

    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = currency
    >>> shipment_out.save()
    >>> shipment_out.click('wait')
    >>> shipment_out.click('assign_try')
    >>> shipment_out.click('pick')
    >>> shipment_out.click('pack')
    >>> shipment_out.click('do')

Testing the reports::

    >>> delivery_note = Report('stock.shipment.out.delivery_note')
    >>> ext, _, _, name = delivery_note.execute([shipment_out], {})
    >>> ext
    'odt'
    >>> name
    'Delivery Note-1'

    >>> picking_list = Report('stock.shipment.out.picking_list')
    >>> ext, _, _, name = picking_list.execute([shipment_out], {})
    >>> ext
    'odt'
    >>> name
    'Picking List-1'

Create an internal shipment::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> shipment_internal = ShipmentInternal()
    >>> shipment_internal.planned_date = today
    >>> shipment_internal.from_location = storage_loc
    >>> shipment_internal.to_location = lost_loc
    >>> move = shipment_internal.moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = lost_loc
    >>> shipment_internal.save()
    >>> shipment_internal.click('wait')
    >>> shipment_internal.click('assign_try')
    >>> shipment_internal.click('do')

Testing the report::

    >>> internal_report = Report('stock.shipment.internal.report')
    >>> ext, _, _, name = internal_report.execute([shipment_internal], {})
    >>> ext
    'odt'
    >>> name
    'Internal Shipment-1'

