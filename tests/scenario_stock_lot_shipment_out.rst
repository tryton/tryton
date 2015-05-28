===============================
Stock Lot Shipment Out Scenario
===============================

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

Install stock_lot Module::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([('name', '=', 'stock_lot')])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

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
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> shipment_out.company = company

Add two shipment lines of same product::

    >>> StockMove = Model.get('stock.move')
    >>> move = StockMove()
    >>> shipment_out.outgoing_moves.append(move)
    >>> move.product = product
    >>> move.uom =unit
    >>> move.quantity = 10
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> move = StockMove()
    >>> shipment_out.outgoing_moves.append(move)
    >>> move.product = product
    >>> move.uom =unit
    >>> move.quantity = 4
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_out.save()

Set the shipment state to waiting::

    >>> shipment_out.click('wait')
    >>> len(shipment_out.outgoing_moves)
    2
    >>> len(shipment_out.inventory_moves)
    2

Assign the shipment with 2 lines of 7 products::

    >>> for move in shipment_out.inventory_moves:
    ...     move.quantity = 7
    >>> shipment_out.click('assign_force')
    >>> shipment_out.state
    u'assigned'

Set 2 lots::

    >>> Lot = Model.get('stock.lot')
    >>> for i, move in enumerate(shipment_out.inventory_moves, start=1):
    ...     lot = Lot(number='%05i' % i, product=product)
    ...     lot.save()
    ...     move.lot = lot
    >>> shipment_out.save()

Pack the shipment::

    >>> shipment_out.click('pack')
    >>> shipment_out.state
    u'packed'
    >>> len(shipment_out.outgoing_moves)
    3
    >>> sorted([m.quantity for m in shipment_out.outgoing_moves])
    [3.0, 4.0, 7.0]
    >>> lot_quantities = {}
    >>> for move in shipment_out.outgoing_moves:
    ...     quantity = lot_quantities.setdefault(move.lot.number, 0)
    ...     lot_quantities[move.lot.number] += move.quantity
    >>> sorted(lot_quantities.items())
    [(u'00001', 7.0), (u'00002', 7.0)]
