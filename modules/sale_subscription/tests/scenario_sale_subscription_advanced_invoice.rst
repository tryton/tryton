================================================
Sale Subscription with Advanced Invoice Scenario
================================================

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

    >>> monthly_in_advance = RecurrenceRuleSet(name='Monthly in advance')
    >>> rule, = monthly_in_advance.rules
    >>> rule.freq = 'monthly'
    >>> rule.interval = 1
    >>> rule.bymonthday = '-1'
    >>> monthly_in_advance.save()

    >>> monthly = RecurrenceRuleSet(name='Monthly')
    >>> rule, = monthly.rules
    >>> rule.freq = 'monthly'
    >>> rule.interval = 1
    >>> rule.bymonthday = '1'
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
    >>> service.consumption_delay = datetime.timedelta(days=-1)
    >>> service.save()

Subscribe with start date greater than invoice start date::

    >>> Subscription = Model.get('sale.subscription')

    >>> subscription = Subscription()
    >>> subscription.party = customer
    >>> subscription.start_date = datetime.date(2016, 2, 1)
    >>> subscription.invoice_start_date = datetime.date(2016, 1, 31)
    >>> subscription.invoice_recurrence = monthly_in_advance
    >>> line = subscription.lines.new()
    >>> line.service = service
    >>> line.quantity = 10

    >>> subscription.click('quote')
    >>> subscription.click('run')
    >>> subscription.reload()
    >>> subscription.next_invoice_date
    datetime.date(2016, 1, 31)
    >>> line, = subscription.lines
    >>> line.next_consumption_date_delayed
    datetime.date(2016, 1, 31)

Create line consumption::

    >>> LineConsumption = Model.get('sale.subscription.line.consumption')

    >>> line_consumption_create = Wizard(
    ...     'sale.subscription.line.consumption.create')
    >>> line_consumption_create.form.date = datetime.date(2016, 1, 31)
    >>> line_consumption_create.execute('create_')

    >>> len(LineConsumption.find([]))
    1

    >>> subscription.reload()
    >>> subscription.next_invoice_date
    datetime.date(2016, 1, 31)
    >>> line, = subscription.lines
    >>> line.next_consumption_date
    datetime.date(2016, 3, 1)
    >>> line.next_consumption_date_delayed
    datetime.date(2016, 2, 29)

Create subscription invoice::

    >>> Invoice = Model.get('account.invoice')

    >>> create_invoice = Wizard('sale.subscription.create_invoice')
    >>> create_invoice.form.date = datetime.date(2016, 1, 31)
    >>> create_invoice.execute('create_')

    >>> invoice, = Invoice.find([])
    >>> line, = invoice.lines
    >>> line.quantity
    10.0

    >>> subscription.reload()
    >>> subscription.next_invoice_date
    datetime.date(2016, 2, 29)

Consume and invoice again::

    >>> line_consumption_create = Wizard(
    ...     'sale.subscription.line.consumption.create')
    >>> line_consumption_create.form.date = datetime.date(2016, 2, 29)
    >>> line_consumption_create.execute('create_')

    >>> len(LineConsumption.find([]))
    2

    >>> subscription.reload()
    >>> subscription.next_invoice_date
    datetime.date(2016, 2, 29)
    >>> line, = subscription.lines
    >>> line.next_consumption_date
    datetime.date(2016, 4, 1)
    >>> line.next_consumption_date_delayed
    datetime.date(2016, 3, 31)

    >>> create_invoice = Wizard('sale.subscription.create_invoice')
    >>> create_invoice.form.date = datetime.date(2016, 2, 29)
    >>> create_invoice.execute('create_')

    >>> invoice2, = Invoice.find([('id', '!=', invoice.id)])
    >>> line, = invoice2.lines
    >>> line.quantity
    10.0

    >>> subscription.reload()
    >>> subscription.next_invoice_date
    datetime.date(2016, 3, 31)