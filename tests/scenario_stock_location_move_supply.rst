==========================
Stock Location Move Supply
==========================

Imports::

    >>> import datetime
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Install stock_location_move and stock_supply::

    >>> config = activate_modules(['stock_location_move', 'stock_supply'])

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> provisioning_loc = Location(
    ...     name="Provisioning Location", parent=warehouse_loc)
    >>> provisioning_loc.save()
    >>> pallet = Location(name="Pallet", parent=provisioning_loc, movable=True)
    >>> pallet.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(0)
    >>> template.save()
    >>> product = Product()
    >>> product.template = template
    >>> product.save()

Create internal order point::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.product = product
    >>> order_point.storage_location = storage_loc
    >>> order_point.provisioning_location = provisioning_loc
    >>> order_point.type = 'internal'
    >>> order_point.min_quantity = 2
    >>> order_point.target_quantity = 2
    >>> order_point.save()

Fill pallet::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = pallet
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 1
    >>> inventory.click('confirm')

Plan moving pallet::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> shipment = ShipmentInternal()
    >>> shipment.planned_date = today
    >>> shipment.from_location = provisioning_loc
    >>> shipment.to_location = storage_loc
    >>> shipment.locations.append(Location(pallet.id))
    >>> shipment.save()

Execute internal supply::

    >>> Wizard('stock.supply').execute('create_')

Only 1 product is requested::

    >>> shipment, = ShipmentInternal.find([
    ...         ('id', '!=', shipment.id),
    ...         ])
    >>> shipment.state
    u'request'
    >>> move, = shipment.moves
    >>> move.quantity
    1.0

Pallet did not moved::

    >>> pallet.reload()
    >>> pallet.parent.name
    u'Provisioning Location'
