======================
Stock Package Scenario
======================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('stock_package', create_company)

    >>> Package = Model.get('stock.package')

Get currency::

    >>> currency = get_currency()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

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

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc

Add two shipment lines of same product::

    >>> StockMove = Model.get('stock.move')
    >>> shipment_out.outgoing_moves.extend([StockMove(), StockMove()])
    >>> for move in shipment_out.outgoing_moves:
    ...     move.product = product
    ...     move.unit = unit
    ...     move.quantity = 2
    ...     move.from_location = output_loc
    ...     move.to_location = customer_loc
    ...     move.unit_price = Decimal('1')
    ...     move.currency = currency
    >>> shipment_out.save()

Pack shipment::

    >>> shipment_out.click('wait')
    >>> shipment_out.click('assign_force')
    >>> shipment_out.click('pick')

Package products::

    >>> PackageType = Model.get('stock.package.type')
    >>> box = PackageType(name='box')
    >>> box.length = 80
    >>> box.length_uom, = ProductUom.find([('name', '=', "Centimeter")])
    >>> box.width = 1
    >>> box.width_uom, = ProductUom.find([('name', '=', "Meter")])
    >>> box.height_uom = box.length_uom
    >>> box.packaging_volume
    >>> box.packaging_volume_uom, = ProductUom.find([('name', '=', "Cubic meter")])
    >>> box.save()

    >>> shipment_pack = Wizard('stock.shipment.pack', [shipment_out])

    >>> shipment_pack.form.type = box
    >>> shipment_pack.form.height = 100
    >>> shipment_pack.execute('add_fill_package')

    >>> package_pack, = shipment_pack.actions
    >>> moves = package_pack.form.allowed_moves
    >>> len(moves)
    2
    >>> package_pack.form.source = moves[0]
    >>> package_pack.execute('add_move')
    >>> package_pack.execute('end')

    >>> shipment_out.reload()
    >>> package, = shipment_out.root_packages

    >>> shipment_pack.form.type = box
    >>> shipment_pack.form.children.append(Package(package.id))
    >>> shipment_pack.form.length
    80.0
    >>> shipment_pack.form.height = 50
    >>> shipment_pack.form.packaging_volume
    0.4

    >>> shipment_pack.execute('add_package')
    Traceback (most recent call last):
        ...
    PackageValidationError: ...

    >>> shipment_pack.form.height = 120
    >>> shipment_pack.form.packaging_volume
    0.96
    >>> shipment_pack.execute('add_package')

    >>> shipment_out.reload()
    >>> shipment_out.click('pack')
    Traceback (most recent call last):
        ...
    PackageError: ...

    >>> package2 = shipment_out.packages.new(type=box)
    >>> shipment_pack.form.type = box
    >>> shipment_pack.execute('add_fill_package')
    >>> package_pack, = shipment_pack.actions
    >>> package_pack.form.source, = package_pack.form.allowed_moves
    >>> package_pack.form.quantity = 1
    >>> package_pack.execute('add_move')
    >>> package_pack.form.source, = package_pack.form.allowed_moves
    >>> package_pack.execute('add_move')
    >>> package_pack.execute('end')
    >>> shipment_pack.execute('end')

    >>> shipment_out.click('pack')
    >>> shipment_out.state
    'packed'
