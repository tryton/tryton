==========================
Stock Shipment Cron Assign
==========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Cron = Model.get('ir.cron')
    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> UoM = Model.get('product.uom')

Get currency::

    >>> currency = get_currency()

Create a product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.save()
    >>> product, = template.products

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Get locations::

    >>> storage_loc, = Location.find([('code', '=', "STO")])
    >>> supplier_loc, = Location.find([('code', '=', "SUP")])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')], limit=1)

Fill storage::

    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 5
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = currency
    >>> move.effective_date = yesterday
    >>> move.click('do')
    >>> move.state
    'done'

Create different shipments with different planned dates::

    >>> shipment_int_1 = ShipmentInternal()
    >>> shipment_int_1.planned_date = today
    >>> shipment_int_1.from_location = storage_loc
    >>> shipment_int_1.to_location = lost_loc
    >>> move = shipment_int_1.moves.new()
    >>> move.from_location = shipment_int_1.from_location
    >>> move.to_location = shipment_int_1.to_location
    >>> move.product = product
    >>> move.quantity = 2
    >>> shipment_int_1.click('wait')
    >>> shipment_int_1.state
    'waiting'

    >>> shipment_out_1 = ShipmentOut()
    >>> shipment_out_1.planned_date = today
    >>> shipment_out_1.customer = customer
    >>> move = shipment_out_1.outgoing_moves.new()
    >>> move.from_location = shipment_out_1.warehouse_output
    >>> move.to_location = shipment_out_1.customer_location
    >>> move.product = product
    >>> move.quantity = 2
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = currency
    >>> shipment_out_1.click('wait')
    >>> shipment_out_1.state
    'waiting'

    >>> shipment_int_2, = shipment_int_1.duplicate()
    >>> shipment_int_2.click('wait')
    >>> shipment_int_2.state
    'waiting'

    >>> shipment_out_2, = shipment_out_1.duplicate()
    >>> shipment_out_2.click('wait')
    >>> shipment_out_2.state
    'waiting'

Run assignation cron::

    >>> cron = Cron(method='ir.cron|stock_shipment_assign_try')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'days'
    >>> cron.click('run_once')

Check assignations::

    >>> shipment_int_1.reload()
    >>> shipment_int_1.state
    'assigned'

    >>> shipment_out_1.reload()
    >>> shipment_out_1.state
    'assigned'

    >>> shipment_int_2.reload()
    >>> shipment_int_2.state
    'waiting'
    >>> shipment_int_2.partially_assigned
    True

    >>> shipment_out_2.reload()
    >>> shipment_out_2.state
    'waiting'
    >>> shipment_out_2.partially_assigned
    False
