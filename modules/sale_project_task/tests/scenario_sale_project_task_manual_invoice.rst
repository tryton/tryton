=========================================
Sale Project Task Manual Invoice Scenario
=========================================

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
    >>> sale.invoice_method = 'fulfillment'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.tasks_state
    'waiting'
    >>> len(sale.invoices)
    0
    >>> sale.invoice_state
    'none'

Complete the task::

    >>> task, = Work.find([])
    >>> task.progress = 1
    >>> task.save()

    >>> sale.reload()
    >>> sale.tasks_state
    'fulfilled'
    >>> len(sale.invoices)
    0

Create invoice::

    >>> sale.click('manual_task_invoice')
    >>> len(sale.invoices)
    1
