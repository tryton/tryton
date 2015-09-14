===========================
Stock Shipment Out Scenario
===========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([('name', '=', 'stock_supply')])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create stock admin user::

    >>> stock_admin_user = User()
    >>> stock_admin_user.name = 'Stock Admin'
    >>> stock_admin_user.login = 'stock_admin'
    >>> stock_admin_user.main_company = company
    >>> stock_admin_group, = Group.find([('name', '=', 'Stock Administration')])
    >>> stock_admin_user.groups.append(stock_admin_group)
    >>> stock_admin_user.save()

Create stock user::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create product user::

    >>> product_admin_user = User()
    >>> product_admin_user.name = 'Product'
    >>> product_admin_user.login = 'product'
    >>> product_admin_user.main_company = company
    >>> product_admin_group, = Group.find([
    ...         ('name', '=', 'Product Administration')
    ...         ])
    >>> product_admin_user.groups.append(product_admin_group)
    >>> product_admin_user.save()

Create product::

    >>> config.user = product_admin_user.id
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

    >>> config.user = stock_admin_user.id
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
    >>> order_point.storage_location = storage_loc
    >>> order_point.provisioning_location = provisioning_loc
    >>> order_point.type = 'internal'
    >>> order_point.min_quantity = 10
    >>> order_point.max_quantity = 15
    >>> order_point.save()

Create inventory to add enough quantity in Provisioning Location::

    >>> config.user = stock_user.id
    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = provisioning_loc
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    u'done'

Execute internal supply::

    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> Wizard('stock.shipment.internal.create').execute('create_')
    >>> shipment, = ShipmentInternal.find([])
    >>> shipment.state
    u'waiting'
    >>> len(shipment.moves)
    1
    >>> move, = shipment.moves
    >>> move.product.template.name
    u'Product'
    >>> move.quantity
    15.0
    >>> move.from_location.name
    u'Provisioning Location'
    >>> move.to_location.code
    u'STO'

Create negative quantity in Second Storage::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = sec_storage_loc
    >>> move.to_location = lost_loc
    >>> move.click('do')
    >>> move.state
    u'done'

Execute internal supply::

    >>> Wizard('stock.shipment.internal.create').execute('create_')
    >>> shipment, = ShipmentInternal.find([('id', '!=', shipment.id)])
    >>> shipment.state
    u'waiting'
    >>> len(shipment.moves)
    1
    >>> move, = shipment.moves
    >>> move.product.template.name
    u'Product'
    >>> move.quantity
    10.0
    >>> move.from_location.name
    u'Provisioning Location'
    >>> move.to_location.name
    u'Second Storage'
