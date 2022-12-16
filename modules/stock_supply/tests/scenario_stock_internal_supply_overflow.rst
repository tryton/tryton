====================================================
Stock supply scenario: Internal supply with overflow
====================================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock_supply')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Using order point to control the overflow
-----------------------------------------

Create the overflow location::

    >>> overflow_loc = Location()
    >>> overflow_loc.name = 'Overflow Location'
    >>> overflow_loc.type = 'storage'
    >>> overflow_loc.parent = warehouse_loc
    >>> overflow_loc.save()

Create the overflowed location::

    >>> overflowed_storage_loc = Location()
    >>> overflowed_storage_loc.name = 'Overflowed Location'
    >>> overflowed_storage_loc.type = 'storage'
    >>> overflowed_storage_loc.parent = warehouse_loc
    >>> overflowed_storage_loc.save()

Create an internal order point::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> overflow_order_point = OrderPoint()
    >>> overflow_order_point.product = product
    >>> overflow_order_point.storage_location = overflowed_storage_loc
    >>> overflow_order_point.overflowing_location = overflow_loc
    >>> overflow_order_point.type = 'internal'
    >>> overflow_order_point.max_quantity = 80
    >>> overflow_order_point.target_quantity = 60
    >>> overflow_order_point.save()

Put too much quantity in the overflowed location::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 100
    >>> move.from_location = lost_loc
    >>> move.to_location = overflowed_storage_loc
    >>> move.click('do')

Execute internal supply::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> Wizard('stock.supply').execute('create_')
    >>> shipment, = ShipmentInternal.find([
    ...         ('to_location', '=', overflow_loc.id),
    ...         ])
    >>> shipment.state
    'request'
    >>> move, = shipment.moves
    >>> move.product.id == product.id
    True
    >>> move.quantity
    40.0
    >>> move.from_location.id == overflowed_storage_loc.id
    True
    >>> move.to_location.id == overflow_loc.id
    True

Using an overflow location
--------------------------

Create the overflowed location::

    >>> sec_overflowed_storage_loc = Location()
    >>> sec_overflowed_storage_loc.name = 'Second Overflowed Location'
    >>> sec_overflowed_storage_loc.type = 'storage'
    >>> sec_overflowed_storage_loc.parent = warehouse_loc
    >>> sec_overflowed_storage_loc.overflowing_location = overflow_loc
    >>> sec_overflowed_storage_loc.save()

Create positive quantity in this location::

    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = lost_loc
    >>> move.to_location = sec_overflowed_storage_loc
    >>> move.click('do')

Execute internal supply::

    >>> Wizard('stock.supply').execute('create_')
    >>> shipment, = ShipmentInternal.find(
    ...     [('from_location', '=', sec_overflowed_storage_loc.id)])
    >>> shipment.state
    'request'
    >>> move, = shipment.moves
    >>> move.product.id == product.id
    True
    >>> move.quantity
    10.0
    >>> move.from_location.id == sec_overflowed_storage_loc.id
    True
    >>> move.to_location.id == overflow_loc.id
    True
