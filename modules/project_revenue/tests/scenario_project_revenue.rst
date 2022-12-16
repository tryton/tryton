========================
Project Revenue Scenario
========================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('project_revenue')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create employee::

    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> _ = employee.cost_prices.new(cost_price=Decimal('10.00'))
    >>> employee.save()
    >>> employee.cost_price
    Decimal('10.00')

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = hour
    >>> template.type = 'service'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('80')
    >>> template.save()
    >>> package, = template.products

Create a Project::

    >>> Project = Model.get('project.work')
    >>> project = Project()
    >>> project.name = 'Test effort'
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.timesheet_available = True
    >>> project.product = product
    >>> project.list_price
    Decimal('20.0000')
    >>> project.effort_duration = datetime.timedelta(hours=1)
    >>> task = project.children.new()
    >>> task.name = 'Task 1'
    >>> task.type = 'task'
    >>> task.timesheet_available = True
    >>> task.product = product
    >>> task.list_price
    Decimal('20.0000')
    >>> task.effort_duration = datetime.timedelta(hours=5)
    >>> task_no_effort = project.children.new()
    >>> task_no_effort.name = "Task 2"
    >>> task_no_effort.type = 'task'
    >>> task_no_effort.effort_duration = None
    >>> task_no_effort.product = package
    >>> task_no_effort.list_price
    Decimal('80.0000')
    >>> project.save()
    >>> task, task_no_effort = project.children

Check project revenue and cost::

    >>> project.revenue
    Decimal('200.00')
    >>> task.revenue
    Decimal('100.00')
    >>> task_no_effort.revenue
    Decimal('80.00')
    >>> project.cost
    Decimal('0.00')
    >>> task.cost
    Decimal('0.00')
    >>> task_no_effort.cost
    Decimal('0.00')

Create timesheets::

    >>> TimesheetLine = Model.get('timesheet.line')
    >>> line = TimesheetLine()
    >>> line.employee = employee
    >>> line.duration = datetime.timedelta(hours=3)
    >>> line.work, = task.timesheet_works
    >>> line.save()
    >>> line = TimesheetLine()
    >>> line.employee = employee
    >>> line.duration = datetime.timedelta(hours=2)
    >>> line.work, = project.timesheet_works
    >>> line.save()

Cost should take in account timesheet lines::

    >>> project.reload()
    >>> task, task_no_effort = project.children
    >>> project.revenue
    Decimal('200.00')
    >>> task.revenue
    Decimal('100.00')
    >>> task_no_effort.revenue
    Decimal('80.00')
    >>> project.cost
    Decimal('50.00')
    >>> task.cost
    Decimal('30.00')
    >>> task_no_effort.cost
    Decimal('0.00')
