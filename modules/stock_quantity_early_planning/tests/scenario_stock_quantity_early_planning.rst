======================================
Stock Quantity Early Planning Scenario
======================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> week1 = today + dt.timedelta(weeks=1)
    >>> week2 = today + dt.timedelta(weeks=2)
    >>> week3 = today + dt.timedelta(weeks=3)
    >>> week4 = today + dt.timedelta(weeks=4)

Activate modules::

    >>> config = activate_modules('stock_quantity_early_planning', create_company)

    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> Party = Model.get('party.party')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> QuantityEarlyPlan = Model.get('stock.quantity.early_plan')
    >>> ShipmentOut = Model.get('stock.shipment.out')

Get currency::

    >>> currency = get_currency()

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
    >>> _ = template.products.new(cost_price=Decimal('5'))
    >>> template.save()
    >>> product1, product2 = template.products

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])

Plan receiving some products tomorrow and in 2 week::

    >>> def fill(quantity, product, date):
    ...     move = Move()
    ...     move.product = product
    ...     move.quantity = quantity
    ...     move.from_location = supplier_loc
    ...     move.to_location = input_loc
    ...     move.unit_price = product.cost_price
    ...     move.currency = currency
    ...     move.planned_date = date
    ...     move.save()

    >>> fill(5, product1, today)
    >>> fill(10, product1, week2)
    >>> fill(5, product1, week4)
    >>> fill(5, product2, week1)
    >>> fill(5, product2, week2)

Plan to ship some products in 3 weeks::

    >>> shipment_out1 = ShipmentOut()
    >>> shipment_out1.planned_date = week3
    >>> shipment_out1.customer = customer
    >>> move = shipment_out1.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 4
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product1.list_price_used
    >>> move.currency = currency
    >>> move = shipment_out1.outgoing_moves.new()
    >>> move.product = product2
    >>> move.quantity = 6
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product2.list_price_used
    >>> move.currency = currency
    >>> shipment_out1.save()

    >>> shipment_out2 = ShipmentOut()
    >>> shipment_out2.planned_date = week3
    >>> shipment_out2.customer = customer
    >>> move = shipment_out2.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 8
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product1.list_price_used
    >>> move.currency = currency
    >>> shipment_out2.save()

    >>> shipment_out3 = ShipmentOut()
    >>> shipment_out3.planned_date = week4
    >>> shipment_out3.customer = customer
    >>> move = shipment_out3.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 4
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product1.list_price_used
    >>> move.currency = currency
    >>> shipment_out3.save()

    >>> ShipmentOut.click([shipment_out1, shipment_out2, shipment_out3], 'wait')

Generate early planning::

    >>> generate_planning = Wizard('stock.quantity.early_plan.generate')
    >>> generate_planning.execute('generate')

Check early planning::

    >>> plan1, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out1))])
    >>> assertEqual(plan1.earlier_date, week2)
    >>> assertEqual(plan1.earliest_date, today)
    >>> plan1.earliest_percentage
    0.4

    >>> plan2, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out2))])
    >>> assertEqual(plan2.earlier_date, week2)
    >>> assertEqual(plan2.earliest_date, week2)
    >>> plan2.earliest_percentage
    1.0

    >>> plan3, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out3))])
    >>> assertEqual(plan3.earlier_date, week4)
    >>> assertEqual(plan3.earliest_date, today)
    >>> plan3.earliest_percentage
    0.75
