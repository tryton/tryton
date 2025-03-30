===============================
Project Invoice Effort Scenario
===============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import create_payment_term
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('project_invoice', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
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

    >>> ProjectWork = Model.get('project.work')
    >>> project = ProjectWork()
    >>> project.name = 'Test effort'
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.project_invoice_method = 'effort'
    >>> project.product = product
    >>> project.effort_duration = dt.timedelta(hours=1)
    >>> task = project.children.new()
    >>> task.name = 'Task 1'
    >>> task.type = 'task'
    >>> task.product = product
    >>> task.effort_duration = dt.timedelta(hours=5)
    >>> task_no_effort = project.children.new()
    >>> task_no_effort.name = "Task 2"
    >>> task_no_effort.type = 'task'
    >>> task_no_effort.effort_duration = None
    >>> task_fixed = project.children.new()
    >>> task_fixed.name = "Task 2"
    >>> task_fixed.type = 'task'
    >>> task_fixed.effort_duration = dt.timedelta(hours=2)
    >>> task_fixed.product = product_fixed
    >>> project.save()
    >>> task, task_no_effort, task_fixed = project.children

Check project amounts::

    >>> project.reload()
    >>> project.invoiced_amount
    Decimal('0.00')
    >>> project.amount_to_invoice
    Decimal('0.00')

Do 1 task::

    >>> task.progress = 1
    >>> task.save()

Check project amounts::

    >>> project.reload()
    >>> project.invoiced_amount
    Decimal('0.00')
    >>> project.amount_to_invoice
    Decimal('100.00')

Invoice project::

    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('100.00')

Do project::

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

    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('170.00')

Try to change invoice line quantity::

    >>> ProjectWork = Model.get('project.work')
    >>> task = ProjectWork(task.id)
    >>> task.invoice_line.quantity = 1
    >>> task.invoice_line.save()
    Traceback (most recent call last):
        ...
    InvoiceLineValidationError: ...
    >>> task.invoice_line.quantity = 5
    >>> task.invoice_line.save()
