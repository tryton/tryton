=================================
Stock Shipment In Return Scenario
=================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertNotEqual

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock', create_company)

Create supplier::

    >>> Party = Model.get('party.party')
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
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])

Create Shipment In::

    >>> ShipmentInReturn = Model.get('stock.shipment.in.return')
    >>> shipment_return = ShipmentInReturn()
    >>> shipment_return.planned_date = yesterday
    >>> shipment_return.supplier = supplier
    >>> shipment_return.from_location = storage_loc
    >>> move = shipment_return.moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = supplier_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = get_currency()
    >>> shipment_return.save()
    >>> shipment_return.number
    >>> shipment_return.click('wait')
    >>> shipment_return.state
    'waiting'
    >>> assertNotEqual(shipment_return.number, None)

Reschedule shipment::

    >>> Cron = Model.get('ir.cron')
    >>> cron = Cron(method='stock.shipment.in.return|reschedule')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'months'
    >>> cron.click('run_once')
    >>> shipment_return.reload()
    >>> assertEqual(shipment_return.planned_date, today)
