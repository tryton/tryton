================================
Stock Shipment Internal Scenario
================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import (
    ...     activate_modules, assertEqual, assertNotEqual, set_user)

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')
    >>> User = Model.get('res.user')

Set employee::

    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> user = User(config.user)
    >>> user.employees.append(employee)
    >>> user.employee = employee
    >>> user.save()
    >>> set_user(user.id)

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
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
    >>> lost_found_loc, = Location.find([('type', '=', 'lost_found')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> internal_loc = Location(
    ...     name="Internal", type='storage', parent=storage_loc.parent)
    >>> internal_loc.save()

Create Internal Shipment::

    >>> Shipment = Model.get('stock.shipment.internal')
    >>> StockMove = Model.get('stock.move')
    >>> shipment = Shipment()
    >>> shipment.planned_date = today
    >>> shipment.from_location = internal_loc
    >>> shipment.to_location = storage_loc
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = internal_loc
    >>> move.to_location = storage_loc
    >>> shipment.save()
    >>> shipment.number
    >>> shipment.assigned_by
    >>> shipment.done_by

    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> assertNotEqual(shipment.number, None)
    >>> shipment.click('assign_try')
    >>> shipment.state
    'waiting'
    >>> shipment.assigned_by
    >>> shipment.done_by

    >>> report = Report('stock.shipment.internal.report')
    >>> _ = report.execute([shipment])

Create Internal Shipment from lost_found location::

    >>> lost_found_shipment = Shipment()
    >>> lost_found_shipment.planned_date = today
    >>> lost_found_shipment.from_location = lost_found_loc
    >>> lost_found_shipment.to_location = internal_loc
    >>> move = StockMove()
    >>> move = lost_found_shipment.moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 2
    >>> move.from_location = lost_found_loc
    >>> move.to_location = internal_loc
    >>> lost_found_shipment.click('wait')
    >>> lost_found_shipment.click('assign_try')
    >>> lost_found_shipment.state
    'assigned'
    >>> lost_found_shipment.click('do')
    >>> lost_found_shipment.state
    'done'

Check that now we can finish the older shipment::

    >>> shipment.click('assign_try')
    >>> assertEqual(shipment.assigned_by, employee)
    >>> shipment.done_by

    >>> shipment.click('do')
    >>> shipment.state
    'done'
    >>> assertEqual(shipment.done_by, employee)

Duplicate Internal Shipment::

    >>> shipment_copy, = shipment.duplicate()
    >>> len(shipment_copy.moves)
    1

Reschedule shipment::

    >>> shipment_copy.planned_date = yesterday
    >>> shipment_copy.click('wait')
    >>> Cron = Model.get('ir.cron')
    >>> cron = Cron(method='stock.shipment.internal|reschedule')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'months'
    >>> cron.click('run_once')
    >>> shipment_copy.reload()
    >>> assertEqual(shipment_copy.planned_date, today)
