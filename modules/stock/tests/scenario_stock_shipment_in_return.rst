=================================
Stock Shipment In Return Scenario
=================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    >>> move.uom =unit
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = supplier_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_return.click('wait')
    >>> shipment_return.state
    'waiting'

Reschedule shipment::

    >>> Cron = Model.get('ir.cron')
    >>> cron = Cron(method='stock.shipment.in.return|reschedule')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'months'
    >>> cron.click('run_once')
    >>> shipment_return.reload()
    >>> shipment_return.planned_date == today
    True
