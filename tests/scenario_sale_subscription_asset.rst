================================
Sale Subscription Asset Scenario
================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules('sale_subscription_asset')

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

Create some assets::

    >>> ProductTemplate = Model.get('product.template')
    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Asset'
    >>> template.default_uom = unit
    >>> template.type = 'assets'
    >>> template.list_price = Decimal(1000)
    >>> template.save()
    >>> asset, = template.products

And some lots linked to the asset::

    >>> StockLot = Model.get('stock.lot')
    >>> lot1 = StockLot(number='001', product=asset)
    >>> lot1.save()
    >>> lot2 = StockLot(number='002', product=asset)
    >>> lot2.save()

Create subscription recurrence rule sets::

    >>> RecurrenceRuleSet = Model.get('sale.subscription.recurrence.rule.set')

    >>> monthly = RecurrenceRuleSet(name='Monthly')
    >>> rule, = monthly.rules
    >>> rule.freq = 'monthly'
    >>> rule.interval = 1
    >>> monthly.save()

Create subscription service::

    >>> template = ProductTemplate()
    >>> template.name = 'Rental'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('10')
    >>> template.save()
    >>> product, = template.products

    >>> Service = Model.get('sale.subscription.service')
    >>> service = Service()
    >>> service.product = product
    >>> service.asset_lots.extend([lot1, lot2])
    >>> service.save()

    >>> sorted(l.number for l in service.asset_lots_available)
    ['001', '002']

Subscribe::

    >>> Subscription = Model.get('sale.subscription')

    >>> subscription = Subscription()
    >>> subscription.party = customer
    >>> subscription.start_date = datetime.date(2016, 1, 1)
    >>> subscription.invoice_start_date = datetime.date(2016, 2, 1)
    >>> subscription.invoice_recurrence = monthly
    >>> line = subscription.lines.new()
    >>> line.service = service
    >>> line.quantity = 1

    >>> subscription.click('quote')
    >>> subscription.click('run')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    RequiredValidationError: ...

    >>> subscription.click('draft')
    >>> line, = subscription.lines
    >>> line.asset_lot = lot1
    >>> subscription.click('quote')
    >>> subscription.click('run')

    >>> with config.set_context(date=datetime.date(2017, 1, 1)):
    ...     lot1.reload()
    ...     subscribed_line = lot1.subscribed
    ...     service.reload()
    ...     lots_available = sorted(
    ...         l.number for l in service.asset_lots_available)
    >>> subscribed_line == line
    True
    >>> lots_available
    ['002']

Creating an overlapping line won't work::

    >>> overlapping = Subscription()
    >>> overlapping.party = customer
    >>> overlapping.start_date = datetime.date(2017, 1, 1)
    >>> overlapping.invoice_start_date = datetime.date(2017, 2, 1)
    >>> overlapping.invoice_recurrence = monthly
    >>> line = overlapping.lines.new()
    >>> line.service = service
    >>> line.start_date = datetime.date(2017, 1, 1)
    >>> line.quantity = 1
    >>> line.asset_lot = lot1
    >>> overlapping.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    ValidationError: ....

Cancelling the subscription will remove lot from the lines thus making it
available again::

    >>> another_subscription = Subscription()
    >>> another_subscription.party = customer
    >>> another_subscription.start_date = datetime.date(2018, 1, 1)
    >>> another_subscription.invoice_start_date = datetime.date(2018, 2, 1)
    >>> another_subscription.invoice_recurrence = monthly
    >>> line = another_subscription.lines.new()
    >>> line.service = service
    >>> line.asset_lot = lot2
    >>> line.quantity = 1

    >>> another_subscription.click('quote')
    >>> service.reload()
    >>> sorted(l.number for l in service.asset_lots_available)
    []

    >>> another_subscription.click('cancel')
    >>> [l.asset_lot for l in another_subscription.lines]
    [None]
    >>> service.reload()
    >>> sorted(l.number for l in service.asset_lots_available)
    ['002']
