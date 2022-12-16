======================================
Stock Quantity Early Planning Scenario
======================================

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
    >>> week4 = today + relativedelta(weeks=4)

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
    >>> move.unit_price = product1.list_price
    >>> move = shipment_out1.outgoing_moves.new()
    >>> move.product = product2
    >>> move.quantity = 6
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product2.list_price
    >>> shipment_out1.save()

    >>> shipment_out2 = ShipmentOut()
    >>> shipment_out2.planned_date = week3
    >>> shipment_out2.customer = customer
    >>> move = shipment_out2.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 8
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product1.list_price
    >>> shipment_out2.save()

    >>> shipment_out3 = ShipmentOut()
    >>> shipment_out3.planned_date = week4
    >>> shipment_out3.customer = customer
    >>> move = shipment_out3.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 4
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = product1.list_price
    >>> shipment_out3.save()

    >>> ShipmentOut.click([shipment_out1, shipment_out2, shipment_out3], 'wait')

Generate early planning::

    >>> generate_planning = Wizard('stock.quantity.early_plan.generate')
    >>> generate_planning.execute('generate')

Check early planning::

    >>> plan1, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out1))])
    >>> plan1.earlier_date == week2
    True
    >>> plan1.earliest_date == today
    True
    >>> plan1.earliest_percentage
    0.4

    >>> plan2, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out2))])
    >>> plan2.earlier_date == week2
    True
    >>> plan2.earliest_date == week2
    True
    >>> plan2.earliest_percentage
    1.0

    >>> plan3, = QuantityEarlyPlan.find(
    ...     [('origin', '=', str(shipment_out3))])
    >>> plan3.earlier_date == week4
    True
    >>> plan3.earliest_date == today
    True
    >>> plan3.earliest_percentage
    0.75
