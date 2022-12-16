=========================================
Project Invoice Multiple Parties Scenario
=========================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('project_invoice')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create two customers::

    >>> Party = Model.get('party.party')
    >>> customer1 = Party(name='Customer 1')
    >>> customer1.save()
    >>> customer2 = Party(name='Customer 2')
    >>> customer2.save()

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

Create a Project with multiple customers::

    >>> ProjectWork = Model.get('project.work')
    >>> project = ProjectWork()
    >>> project.name = 'Test multiple party'
    >>> project.type = 'project'
    >>> project.party = customer1
    >>> project.project_invoice_method = 'effort'
    >>> project.product = product
    >>> project.effort_duration = datetime.timedelta(hours=1)

    >>> subproject = project.children.new()
    >>> subproject.name = 'Subproject'
    >>> subproject.type = 'project'
    >>> subproject.party = customer2
    >>> subproject.project_invoice_method = 'effort'
    >>> subproject.product = product
    >>> subproject.effort_duration = datetime.timedelta(hours=5)

    >>> project.save()
    >>> subproject, = project.children

Check project amounts::

    >>> project.reload()
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('0')

Do project and subproject::

    >>> subproject.progress = 1
    >>> subproject.save()
    >>> project.progress = 1
    >>> project.save()

Check project amounts::

    >>> project.reload()
    >>> project.amount_to_invoice
    Decimal('120.00')
    >>> project.invoiced_amount
    Decimal('0')

Invoice project::

    >>> project.click('invoice')
    >>> project.amount_to_invoice
    Decimal('0.00')
    >>> project.invoiced_amount
    Decimal('120.00')

    >>> Invoice = Model.get('account.invoice')
    >>> invoices = Invoice.find([])
    >>> len(invoices)
    2
    >>> sorted([i.party.name for i in invoices])
    ['Customer 1', 'Customer 2']
