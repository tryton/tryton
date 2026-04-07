==================================
Production Work Timesheet Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> include_timesheet_cost = globals().get('include_timesheet_cost', False)
    >>> cost = Decimal('80.0000') if include_timesheet_cost else Decimal('10.0000')

Activate modules::

    >>> config = activate_modules(
    ...     ['production_work_timesheet', 'timesheet_cost'])

    >>> Employee = Model.get('company.employee')
    >>> Operation = Model.get('production.routing.operation')
    >>> Party = Model.get('party.party')
    >>> Production = Model.get('production')
    >>> WorkCenter = Model.get('production.work.center')

Create company::

    >>> _ = create_company()

Create employee::

    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> cost_price = employee.cost_prices.new()
    >>> cost_price.cost_price = Decimal('35.00')
    >>> employee.save()

Create work center and operation::

    >>> work_center = WorkCenter(name="Work Center")
    >>> work_center.cost_price = Decimal('10')
    >>> work_center.cost_method = 'cycle'
    >>> work_center.include_timesheet_cost = include_timesheet_cost
    >>> work_center.save()

    >>> operation = Operation(name="Operation")
    >>> operation.timesheet_available = True
    >>> operation.save()

Make a production::

    >>> production = Production()
    >>> work = production.works.new()
    >>> work.operation = operation
    >>> work.work_center = work_center
    >>> production.click('wait')
    >>> production.state
    'waiting'
    >>> production.cost
    Decimal('0.0000')

Run the production::

    >>> production.click('assign_try')
    >>> production.click('run')
    >>> production.state
    'running'
    >>> work, = production.works
    >>> work.click('start')
    >>> work_line = work.timesheet_lines.new()
    >>> work_line.employee = employee
    >>> work_line.duration = dt.timedelta(hours=2)
    >>> work.click('stop')
    >>> work.state
    'finished'

Check production cost::

    >>> production.reload()
    >>> assertEqual(production.cost, cost)
    >>> work, = production.works
    >>> assertEqual(work.cost, cost)

Do the production::

    >>> production.click('do')
    >>> production.state
    'done'

Check production cost::

    >>> production.reload()
    >>> assertEqual(production.cost, cost)
    >>> work, = production.works
    >>> assertEqual(work.cost, cost)
