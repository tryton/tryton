==================================
Project Invoice Timesheet Scenario
==================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install project_invoice::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'project_invoice'),
    ...     ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create project user::

    >>> project_user = User()
    >>> project_user.name = 'Project'
    >>> project_user.login = 'project'
    >>> project_user.main_company = company
    >>> project_group, = Group.find([('name', '=', 'Project Administration')])
    >>> timesheet_group, = Group.find([('name', '=', 'Timesheet Administration')])
    >>> project_user.groups.extend([project_group, timesheet_group])
    >>> project_user.save()

Create project invoice user::

    >>> project_invoice_user = User()
    >>> project_invoice_user.name = 'Project Invoice'
    >>> project_invoice_user.login = 'project_invoice'
    >>> project_invoice_user.main_company = company
    >>> project_invoice_group, = Group.find([('name', '=', 'Project Invoice')])
    >>> project_group, = Group.find([('name', '=', 'Project Administration')])
    >>> project_invoice_user.groups.extend(
    ...     [project_invoice_group, project_group])
    >>> project_invoice_user.save()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.customer_payment_term = payment_term
    >>> customer.save()

Create employee::

    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> employee.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = hour
    >>> template.type = 'service'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('5')
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create a Project::

    >>> config.user = project_user.id
    >>> ProjectWork = Model.get('project.work')
    >>> TimesheetWork = Model.get('timesheet.work')
    >>> project = ProjectWork()
    >>> project.name = 'Test timesheet'
    >>> work = TimesheetWork()
    >>> work.name = 'Test timesheet'
    >>> work.save()
    >>> project.work = work
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.project_invoice_method = 'timesheet'
    >>> project.product = product
    >>> task = ProjectWork()
    >>> task.name = 'Task 1'
    >>> work = TimesheetWork()
    >>> work.name = 'Task 1'
    >>> work.save()
    >>> task.work = work
    >>> task.type = 'task'
    >>> task.product = product
    >>> project.children.append(task)
    >>> project.save()
    >>> task, = project.children

Add a task without timesheet work::

    >>> task2 = project.children.new()
    >>> task2.name = 'Task 2'
    >>> task2.type = 'task'
    >>> project.save()

Create timesheets::

    >>> TimesheetLine = Model.get('timesheet.line')
    >>> line = TimesheetLine()
    >>> line.employee = employee
    >>> line.duration = datetime.timedelta(hours=3)
    >>> line.work = task.work
    >>> line.save()
    >>> line = TimesheetLine()
    >>> line.employee = employee
    >>> line.duration = datetime.timedelta(hours=2)
    >>> line.work = project.work
    >>> line.save()

Check project duration::

    >>> project.reload()
    >>> project.invoiced_duration
    datetime.timedelta(0)
    >>> project.duration_to_invoice
    datetime.timedelta(0, 18000)
    >>> project.invoiced_amount
    Decimal('0.00')

Invoice project::

    >>> config.user = project_invoice_user.id
    >>> project.click('invoice')
    >>> project.invoiced_duration
    datetime.timedelta(0, 18000)
    >>> project.duration_to_invoice
    datetime.timedelta(0)
    >>> project.invoiced_amount
    Decimal('100.00')

Create more timesheets::

    >>> config.user = project_user.id
    >>> TimesheetLine = Model.get('timesheet.line')
    >>> line = TimesheetLine()
    >>> line.employee = employee
    >>> line.duration = datetime.timedelta(hours=4)
    >>> line.work = task.work
    >>> line.save()

Check project duration::

    >>> project.reload()
    >>> project.invoiced_duration
    datetime.timedelta(0, 18000)
    >>> project.duration_to_invoice
    datetime.timedelta(0, 14400)
    >>> project.invoiced_amount
    Decimal('100.00')

Invoice again project::

    >>> config.user = project_invoice_user.id
    >>> project.click('invoice')
    >>> project.invoiced_duration
    datetime.timedelta(0, 32400)
    >>> project.duration_to_invoice
    datetime.timedelta(0)
    >>> project.invoiced_amount
    Decimal('180.00')
