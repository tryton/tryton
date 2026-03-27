==========================================
Sale Project Task Manual Creation Scenario
==========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_project_task', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> UoM = Model.get('product.uom')
    >>> Work = Model.get('project.work')

Create a customer party::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create a service product with tasks::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> account_category = ProductCategory(name="Accounting")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = get_accounts()['revenue']
    >>> account_category.save()

    >>> product_template = ProductTemplate(name="Service")
    >>> product_template.type = 'service'
    >>> product_template.default_uom = unit
    >>> product_template.account_category = account_category
    >>> product_template.salable = True
    >>> product_template.list_price = Decimal('500.0000')
    >>> product_template.taskable = True
    >>> task = product_template.tasks.new(name="Task")
    >>> task.timesheet_available = True
    >>> product_template.save()
    >>> product, = product_template.products

Sale service::

    >>> sale = Sale(party=customer)
    >>> sale.task_creation_method = 'manual'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.tasks_state
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.tasks_state
    >>> bool(sale.tasks_to_create)
    True
    >>> line, = sale.lines
    >>> line.quantity_task_to_create
    1.0
    >>> len(line.tasks)
    0

Create tasks::

    >>> sale.click('manual_task_creation')
    >>> line, = sale.lines
    >>> len(line.tasks)
    1
    >>> sale.tasks_state
    'waiting'
    >>> bool(sale.tasks_to_create)
    False
    >>> line.quantity_task_to_create
    0.0
