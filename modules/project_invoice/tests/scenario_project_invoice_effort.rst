===============================
Project Invoice Effort Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     create_payment_term
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('project_invoice')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create project user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
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

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = hour
    >>> template.type = 'service'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'Service Fixed'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('50')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product_fixed, = template.products

Create a Project::

    >>> set_user(project_user)
    >>> ProjectWork = Model.get('project.work')
    >>> project = ProjectWork()
    >>> project.name = 'Test effort'
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.project_invoice_method = 'effort'
    >>> project.product = product
    >>> project.effort_duration = datetime.timedelta(hours=1)
    >>> task = project.children.new()
    >>> task.name = 'Task 1'
    >>> task.type = 'task'
    >>> task.product = product
    >>> task.effort_duration = datetime.timedelta(hours=5)
    >>> task_no_effort = project.children.new()
    >>> task_no_effort.name = "Task 2"
    >>> task_no_effort.type = 'task'
    >>> task_no_effort.effort_duration = None
    >>> task_fixed = project.children.new()
    >>> task_fixed.name = "Task 2"
    >>> task_fixed.type = 'task'
    >>> task_fixed.effort_duration = datetime.timedelta(hours=2)
    >>> task_fixed.product = product_fixed
    >>> project.save()
    >>> task, task_no_effort, task_fixed = project.children

Check project amounts::

    >>> project.reload()
    >>> project.invoiced_amount
    Decimal('0')
    >>> project.amount_to_invoice
    Decimal('0.00')

Do 1 task::

    >>> task.progress = 1
    >>> task.save()

Check project amounts::

    >>> project.reload()
    >>> project.invoiced_amount
    Decimal('0')
    >>> project.amount_to_invoice
    Decimal('100.00')

Invoice project::

    >>> set_user(project_invoice_user)
    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('100.00')

Do project::

    >>> set_user(project_user)
    >>> task_no_effort.progress = 1
    >>> task_no_effort.save()
    >>> task_fixed.progress = 1
    >>> task_fixed.save()
    >>> project.progress = 1
    >>> project.save()

Check project amounts::

    >>> project.reload()
    >>> project.amount_to_invoice
    Decimal('70.00')
    >>> project.invoiced_amount
    Decimal('100.00')

Invoice again project::

    >>> set_user(project_invoice_user)
    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('170.00')
