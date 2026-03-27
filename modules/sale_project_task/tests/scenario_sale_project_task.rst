==========================
Sale Project Task Scenario
==========================

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
    >>> _ = task.children.new(name="Child 1")
    >>> _ = task.children.new(name="Child 2")
    >>> product_template.save()
    >>> product, = product_template.products

Sale service::

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.tasks_state
    >>> line, = sale.lines
    >>> len(line.tasks)
    0
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> line, = sale.lines
    >>> len(line.tasks)
    3
    >>> sale.tasks_state
    'waiting'

Progress some tasks::

    >>> tasks = Work.find([])
    >>> for task in tasks:
    ...     task.progress = .5
    >>> Work.save(tasks)

    >>> sale.reload()
    >>> sale.tasks_state
    'waiting'
    >>> line, = sale.lines
    >>> line.tasks_progress
    0.5

Complete some tasks::

    >>> task, = Work.find([], limit=1)
    >>> task.progress = 1
    >>> task.save()

    >>> sale.reload()
    >>> sale.tasks_state
    'partially'

Complete all tasks::

    >>> tasks = Work.find([])
    >>> for task in tasks:
    ...     task.progress = 1
    >>> Work.save(tasks)

    >>> sale.reload()
    >>> sale.tasks_state
    'fulfilled'
    >>> line, = sale.lines
    >>> line.tasks_progress
    1.0
