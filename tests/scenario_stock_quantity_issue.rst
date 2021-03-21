=============================
Stock Quantity Issue Scenario
=============================

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

    >>> config = activate_modules('stock_quantity_issue')

    >>> Company = Model.get('company.company')
    >>> Cron = Model.get('ir.cron')
    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> QuantityIssue = Model.get('stock.quantity.issue')
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
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])

Plan receiving some products tomorrow and in 2 week::

    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 6
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('5')
    >>> move.planned_date = today
    >>> move.save()

    >>> move, = Move.duplicate(
    ...     [move], default={
    ...         'quantity': 14,
    ...         'planned_date': week2,
    ...         })

Plan to ship some products in 1 week::

    >>> shipment_out1 = ShipmentOut()
    >>> shipment_out1.planned_date = week1
    >>> shipment_out1.customer = customer
    >>> move = shipment_out1.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 6
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20')
    >>> shipment_out1.save()

    >>> shipment_out2, = ShipmentOut.duplicate([shipment_out1])
    >>> shipment_out3, = ShipmentOut.duplicate(
    ...     [shipment_out1], default={'planned_date': week3})

    >>> ShipmentOut.click(
    ...     [shipment_out1, shipment_out2, shipment_out3], 'wait')

Generate quantity issues::

    >>> cron_generate_issues = Cron(method='stock.quantity.issue|generate_issues')
    >>> cron_generate_issues.interval_number = 1
    >>> cron_generate_issues.interval_type = 'days'
    >>> cron_generate_issues.click('run_once')

Check quantity issues::

    >>> issues = QuantityIssue.find([('state', '=', 'open')])
    >>> len(issues)
    2
    >>> issue1, = [i for i in issues if i.origin == shipment_out1]
    >>> issue2, = [i for i in issues if i.origin == shipment_out2]

    >>> issue1.priority
    7
    >>> issue2.priority
    7

    >>> product, = issue1.products
    >>> product.quantity, product.forecast_quantity
    (0.0, -6.0)

    >>> issue1.best_planned_date == week2
    True

Apply best planned date to first shipment::

    >>> issue1.click('process')
    >>> issue1.click('solve')  #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    QuantityIssueError: ...

    >>> issue1.click('apply_best_planned_date')
    >>> issue1.click('solve')

Second shipment does not need to be updated::

    >>> product, = issue2.products
    >>> product.quantity, product.forecast_quantity
    (0.0, 0.0)

Regenerate quantity issues::

    >>> cron_generate_issues.click('run_once')

    >>> issues = QuantityIssue.find([('state', '=', 'open')])
    >>> len(issues)
    0
