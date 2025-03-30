===========================
Stock Shipment Out Scenario
===========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_supply', create_company)

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

Create provisioning location::

    >>> Location = Model.get('stock.location')
    >>> provisioning_loc = Location()
    >>> provisioning_loc.name = 'Provisioning Location'
    >>> provisioning_loc.type = 'storage'
    >>> provisioning_loc.parent = warehouse_loc
    >>> provisioning_loc.save()

Create a new storage location::

    >>> sec_storage_loc = Location()
    >>> sec_storage_loc.name = 'Second Storage'
    >>> sec_storage_loc.type = 'storage'
    >>> sec_storage_loc.parent = warehouse_loc
    >>> sec_storage_loc.provisioning_location = provisioning_loc
    >>> sec_storage_loc.save()

Create internal order point::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.product = product
    >>> order_point.location = storage_loc
    >>> order_point.provisioning_location = provisioning_loc
    >>> order_point.type = 'internal'
    >>> order_point.min_quantity = 10
    >>> order_point.target_quantity = 15
    >>> order_point.save()

Create inventory to add enough quantity in Provisioning Location::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = provisioning_loc
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Execute internal supply::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> Wizard('stock.supply').execute('create_')
    >>> shipment, = ShipmentInternal.find([])
    >>> shipment.state
    'request'
    >>> len(shipment.moves)
    1
    >>> move, = shipment.moves
    >>> move.product.template.name
    'Product'
    >>> move.quantity
    15.0
    >>> move.from_location.name
    'Provisioning Location'
    >>> move.to_location.code
    'STO'

Create negative quantity in Second Storage::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = sec_storage_loc
    >>> move.to_location = lost_loc
    >>> move.click('do')
    >>> move.state
    'done'

Execute internal supply::

    >>> Wizard('stock.supply').execute('create_')
    >>> shipment, = ShipmentInternal.find(
    ...     [('to_location', '=', sec_storage_loc.id)])
    >>> shipment.state
    'request'
    >>> len(shipment.moves)
    1
    >>> move, = shipment.moves
    >>> move.product.template.name
    'Product'
    >>> move.quantity
    10.0
    >>> move.from_location.name
    'Provisioning Location'
    >>> move.to_location.name
    'Second Storage'

Create stock_supply cron and execute it::

    >>> Cron = Model.get('ir.cron')
    >>> shipment.delete()
    >>> cron = Cron(method='stock.order_point|supply_stock')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'months'
    >>> cron.click('run_once')
    >>> shipment, = ShipmentInternal.find(
    ...     [('to_location', '=', sec_storage_loc.id)])
    >>> shipment.state
    'request'
