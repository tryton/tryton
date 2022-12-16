===================================
Sale Subscription New Line Scenario
===================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules('sale_subscription')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create party::

    >>> Party = Model.get('party.party')

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create subscription recurrence rule sets::

    >>> RecurrenceRuleSet = Model.get('sale.subscription.recurrence.rule.set')

    >>> monthly = RecurrenceRuleSet(name='Monthly')
    >>> rule, = monthly.rules
    >>> rule.freq = 'monthly'
    >>> rule.interval = 1
    >>> monthly.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create subscription service::

    >>> Service = Model.get('sale.subscription.service')
    >>> ProductTemplate = Model.get('product.template')
    >>> Uom = Model.get('product.uom')

    >>> unit, = Uom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Rental'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> service = Service()
    >>> service.product = product
    >>> service.consumption_recurrence = monthly
    >>> service.save()

Subscribe::

    >>> Subscription = Model.get('sale.subscription')

    >>> subscription = Subscription()
    >>> subscription.party = customer
    >>> subscription.start_date = datetime.date(2019, 1, 1)
    >>> subscription.invoice_recurrence = monthly
    >>> line = subscription.lines.new()
    >>> line.service = service
    >>> line.quantity = 1
    >>> subscription.click('quote')
    >>> subscription.state
    'quotation'
    >>> subscription.click('run')
    >>> subscription.state
    'running'

Create consumption for next two months::

    >>> LineConsumption = Model.get('sale.subscription.line.consumption')

    >>> line_consumption_create = Wizard(
    ...     'sale.subscription.line.consumption.create')
    >>> line_consumption_create.form.date = datetime.date(2019, 2, 1)
    >>> line_consumption_create.execute('create_')

    >>> len(LineConsumption.find([]))
    2

Create invoice for next two months::

    >>> Invoice = Model.get('account.invoice')

    >>> create_invoice = Wizard('sale.subscription.create_invoice')
    >>> create_invoice.form.date = datetime.date(2019, 2, 1)
    >>> create_invoice.execute('create_')

    >>> invoice, = Invoice.find([])
    >>> line, = invoice.lines
    >>> line.quantity
    2.0
    >>> line.unit_price
    Decimal('10.0000')

Close subscription::

    >>> subscription.click('draft')
    >>> subscription.state
    'draft'
    >>> line, = subscription.lines
    >>> line.consumed_until
    datetime.date(2019, 2, 28)
    >>> line.end_date = datetime.date(2019, 2, 28)
    >>> new_line = subscription.lines.new()
    >>> new_line.service = service
    >>> new_line.quantity = 1
    >>> new_line.start_date = datetime.date(2019, 3, 1)
    >>> new_line.unit_price = Decimal('15.00')
    >>> subscription.click('quote')
    >>> subscription.click('run')
    >>> subscription.state
    'running'

    >>> line_consumption_create = Wizard(
    ...     'sale.subscription.line.consumption.create')
    >>> line_consumption_create.form.date = datetime.date(2019, 3, 1)
    >>> line_consumption_create.execute('create_')

    >>> len(LineConsumption.find([]))
    3

Create next invoice::

    >>> Invoice = Model.get('account.invoice')

    >>> create_invoice = Wizard('sale.subscription.create_invoice')
    >>> create_invoice.form.date = datetime.date(2019, 3, 1)
    >>> create_invoice.execute('create_')

    >>> new_invoice, = Invoice.find([('id', '!=', invoice.id)])
    >>> line, = new_invoice.lines
    >>> line.quantity
    1.0
    >>> line.unit_price
    Decimal('15.00')
