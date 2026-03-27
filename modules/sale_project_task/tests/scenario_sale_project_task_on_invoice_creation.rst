==============================================
Sale Project Task On Invoice Creation Scenario
==============================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_project_task', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> UoM = Model.get('product.uom')
    >>> Work = Model.get('project.work')

Get accounts::


    >>> accounts = get_accounts()

    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.save()

    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = cash_journal
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

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
    >>> sale.task_creation_method = 'invoice'
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
    False
    >>> line, = sale.lines
    >>> line.quantity_task_to_create
    0.0
    >>> len(line.tasks)
    0

Post and pay the invoice::

    >>> invoice, = sale.invoices
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> pay = invoice.click('pay')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> invoice.state
    'paid'

Check tasks are created::

    >>> sale.reload()
    >>> line, = sale.lines
    >>> len(line.tasks)
    1
