===============================================
Stock Quantity Early Planning Incoming Scenario
===============================================

Imports::

    >>> from decimal import Decimal

    >>> import datetime as dt
    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

    >>> today = dt.date.today()
    >>> week1 = today + relativedelta(weeks=1)
    >>> week2 = today + relativedelta(weeks=2)
    >>> week3 = today + relativedelta(weeks=3)

Activate modules::

    >>> config = activate_modules('stock_quantity_early_planning')

    >>> Company = Model.get('company.company')
    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> Party = Model.get('party.party')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> QuantityEarlyPlan = Model.get('stock.quantity.early_plan')
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> ShipmentInternal = Model.get('stock.shipment.internal')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Duplicate warehouse::

    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> warehouse2, = warehouse.duplicate()

Plan receiving some products in 1 week in second warehouse::

    >>> def fill(quantity, product, date):
    ...     move = Move()
    ...     move.product = product
    ...     move.quantity = quantity
    ...     move.from_location = supplier_loc
    ...     move.to_location = warehouse2.input_location
    ...     move.unit_price = product.cost_price
    ...     move.planned_date = date
    ...     move.save()

    >>> fill(5, product, today)
    >>> fill(15, product, week1)

Request to ship to first warehouse in 2 and 3 weeks::

    >>> shipment_int1 = ShipmentInternal()
    >>> shipment_int1.planned_date = week2
    >>> shipment_int1.from_location = warehouse2.storage_location
    >>> shipment_int1.to_location = warehouse.storage_location
    >>> move = shipment_int1.moves.new()
    >>> move.from_location = warehouse2.storage_location
    >>> move.to_location = warehouse.storage_location
    >>> move.product = product
    >>> move.quantity = 10
    >>> shipment_int1.save()
    >>> ShipmentInternal.write(
    ...     [shipment_int1.id], {'state': 'request'}, shipment_int1._context)

    >>> shipment_int2 = ShipmentInternal()
    >>> shipment_int2.planned_date = week2
    >>> shipment_int2.from_location = warehouse2.storage_location
    >>> shipment_int2.to_location = warehouse.storage_location
    >>> move = shipment_int2.moves.new()
    >>> move.from_location = warehouse2.storage_location
    >>> move.to_location = warehouse.storage_location
    >>> move.product = product
    >>> move.quantity = 5
    >>> shipment_int2.save()
    >>> ShipmentInternal.write(
    ...     [shipment_int2.id], {'state': 'request'}, shipment_int2._context)

Plan to ship in 3 weeks::

    >>> shipment_out = ShipmentOut(warehouse=warehouse)
    >>> shipment_out.planned_date = week3
    >>> shipment_out.customer = customer
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 7
    >>> move.from_location = warehouse.output_location
    >>> move.to_location = customer_loc
    >>> move.unit_price = product.list_price
    >>> shipment_out.save()
    >>> shipment_out.click('wait')

Generate early planning::

    >>> generate_planning = Wizard('stock.quantity.early_plan.generate')
    >>> generate_planning.execute('generate')

Check early planning::

    >>> plan, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_int1))])
    >>> plan.earlier_date == week1
    True

    >>> plan, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_int2))])
    >>> plan.earlier_date == today
    True

    >>> plan, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out))])
    >>> plan.earlier_date == week1
    True
