=================================
Stock Shipment Reporting Scenario
=================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([('name', '=', 'stock')])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

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
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.save()
    >>> product.template = template
    >>> product.save()

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
    >>> shipment_in.company = company

Receive a bunch of products::

    >>> move = shipment_in.incoming_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 100
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_in.save()
    >>> shipment_in.click('receive')
    >>> shipment_in.click('done')

Testing the report::

    >>> supplier_restocking_list = Report('stock.shipment.in.restocking_list')
    >>> ext, _, _, name = supplier_restocking_list.execute([shipment_in], {})
    >>> ext
    u'odt'
    >>> name
    u'Restocking List'

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> shipment_out.company = company

Add two shipment lines of same product and go through the workflow::

    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_out.save()
    >>> shipment_out.click('wait')
    >>> shipment_out.click('assign_try')
    True
    >>> shipment_out.click('pack')
    >>> shipment_out.click('done')

Testing the reports::

    >>> delivery_note = Report('stock.shipment.out.delivery_note')
    >>> ext, _, _, name = delivery_note.execute([shipment_out], {})
    >>> ext
    u'odt'
    >>> name
    u'Delivery Note'

    >>> picking_list = Report('stock.shipment.out.picking_list')
    >>> ext, _, _, name = picking_list.execute([shipment_out], {})
    >>> ext
    u'odt'
    >>> name
    u'Picking List'

Create an internal shipment::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> shipment_internal = ShipmentInternal()
    >>> shipment_internal.planned_date = today
    >>> shipment_internal.company = company
    >>> shipment_internal.from_location = storage_loc
    >>> shipment_internal.to_location = lost_loc
    >>> move = shipment_internal.moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = lost_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_internal.save()
    >>> shipment_internal.click('wait')
    >>> shipment_internal.click('assign_try')
    True
    >>> shipment_internal.click('done')

Testing the report::

    >>> internal_report = Report('stock.shipment.internal.report')
    >>> ext, _, _, name = internal_report.execute([shipment_internal], {})
    >>> ext
    u'odt'
    >>> name
    u'Internal Shipment'

