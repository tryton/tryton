==================================
Project Invoice Timesheet Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import create_payment_term
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

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

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> hour, = ProductUom.find([('name', '=', 'Hour')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = hour
    >>> template.type = 'service'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create a Project::

    >>> ProjectWork = Model.get('project.work')
    >>> project = ProjectWork()
    >>> project.name = 'Test timesheet'
    >>> project.type = 'project'
    >>> project.party = customer
    >>> project.project_invoice_method = 'timesheet'
    >>> project.product = product
    >>> project.timesheet_available = True
    >>> task = ProjectWork()
    >>> task.name = 'Task 1'
    >>> task.timesheet_available = True
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
    >>> line.date = yesterday
    >>> line.employee = employee
    >>> line.duration = dt.timedelta(hours=3)
    >>> line.work, = task.timesheet_works
    >>> line.save()
    >>> line = TimesheetLine()
    >>> line.date = today
    >>> line.employee = employee
    >>> line.duration = dt.timedelta(hours=2)
    >>> line.work, = project.timesheet_works
    >>> line.save()

Check project amounts::

    >>> project.reload()
    >>> project.amount_to_invoice
    Decimal('100.00')
    >>> project.invoiced_amount
    Decimal('0.00')

Invoice project up to yesterday::

    >>> project.project_invoice_timesheet_up_to = yesterday
    >>> project.save()
    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('60.00')

    >>> project.project_invoice_timesheet_up_to = today
    >>> project.save()
    >>> project.amount_to_invoice
    Decimal('40.00')

    >>> Invoice = Model.get('account.invoice')
    >>> invoice, = Invoice.find([])
    >>> invoice.total_amount
    Decimal('60.00')

Invoice all project::

    >>> project.project_invoice_timesheet_up_to = None
    >>> project.save()
    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('100.00')

    >>> _, invoice = Invoice.find([], order=[('id', 'ASC')])
    >>> invoice.total_amount
    Decimal('40.00')

Create more timesheets::

    >>> TimesheetLine = Model.get('timesheet.line')
    >>> line = TimesheetLine()
    >>> line.employee = employee
    >>> line.duration = dt.timedelta(hours=4)
    >>> line.work, = task.timesheet_works
    >>> line.save()

Check project amounts::

    >>> project.reload()
    >>> project.amount_to_invoice
    Decimal('80.00')
    >>> project.invoiced_amount
    Decimal('100.00')

Invoice again project::

    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('180.00')

    >>> _, _, invoice = Invoice.find([], order=[('id', 'ASC')])
    >>> invoice.total_amount
    Decimal('80.00')

Try to change invoice line quantity::

    >>> TimesheetLine = Model.get('timesheet.line')
    >>> line = TimesheetLine(line.id)
    >>> line.invoice_line.quantity = 5
    >>> line.invoice_line.save()
    Traceback (most recent call last):
        ...
    InvoiceLineValidationError: ...
    >>> line.invoice_line.quantity = 4
    >>> line.invoice_line.save()
