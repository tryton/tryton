===========================
Purchase Reporting Scenario
===========================

Imports::

    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate modules::

    >>> config = activate_modules('purchase')
    >>> Party = Model.get('party.party')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Purchase = Model.get('purchase.purchase')
    >>> Supplier = Model.get('purchase.reporting.supplier')
    >>> SupplierTimeseries = Model.get(
    ...     'purchase.reporting.supplier.time_series')
    >>> Product = Model.get('purchase.reporting.product')
    >>> ProductTimeseries = Model.get('purchase.reporting.product.time_series')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']

Create parties::

    >>> supplier1 = Party(name='Supplier1')
    >>> supplier1.save()
    >>> supplier2 = Party(name='Supplier2')
    >>> supplier2.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template1 = ProductTemplate()
    >>> template1.name = "Product1"
    >>> template1.default_uom = unit
    >>> template1.type = 'service'
    >>> template1.purchasable = True
    >>> template1.list_price = Decimal('20')
    >>> template1.save()
    >>> product1, = template1.products

    >>> template2, = template1.duplicate(default={'name': "Product2"})
    >>> product2, = template2.products

Create purchases::

    >>> purchase1 = Purchase()
    >>> purchase1.party = supplier1
    >>> purchase1.purchase_date = fiscalyear.start_date
    >>> line = purchase1.lines.new()
    >>> line.product = product1
    >>> line.quantity = 2
    >>> line.unit_price = Decimal('10.0000')
    >>> line = purchase1.lines.new()
    >>> line.product = product2
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10.0000')
    >>> purchase1.click('quote')
    >>> purchase1.click('confirm')

    >>> purchase2 = Purchase()
    >>> purchase2.party = supplier2
    >>> purchase2.purchase_date = (
    ...     fiscalyear.start_date + relativedelta(months=1))
    >>> line = purchase2.lines.new()
    >>> line.product = product1
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10.0000')
    >>> purchase2.click('quote')
    >>> purchase2.click('confirm')

Check purchase reporting per supplier::

    >>> context = dict(
    ...         from_date=fiscalyear.start_date,
    ...         to_date=fiscalyear.end_date,
    ...         period='month')
    >>> with config.set_context(context=context):
    ...     reports = Supplier.find([])
    ...     time_series = SupplierTimeseries.find([])
    >>> len(reports)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.supplier.id, r.number, r.expense) for r in reports) == \
    ...     sorted([(supplier1.id, 1, Decimal('30')),
    ...             (supplier2.id, 1, Decimal('10'))])
    True
    >>> len(time_series)
    2
    >>> purchase1_ts_date = purchase1.purchase_date.replace(day=1)
    >>> purchase2_ts_date = purchase2.purchase_date.replace(day=1)
    >>> with config.set_context(context=context):
    ...     sorted((r.supplier.id, r.date, r.number, r.expense)
    ...         for r in time_series) == sorted(
    ...     [(supplier1.id, purchase1_ts_date, 1, Decimal('30')),
    ...     (supplier2.id, purchase2_ts_date, 1, Decimal('10'))])
    True

Check purchase reporting per product without supplier::

    >>> with config.set_context(context=context):
    ...     reports = Product.find([])
    ...     time_series = ProductTimeseries.find([])
    >>> len(reports)
    0

Check purchase reporting per product with supplier::

    >>> context['supplier'] = supplier1.id
    >>> with config.set_context(context=context):
    ...     reports = Product.find([])
    ...     time_series = ProductTimeseries.find([])
    >>> len(reports)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.product.id, r.number, r.expense) for r in reports) == \
    ...     sorted([(product1.id, 1, Decimal('20')),
    ...         (product2.id, 1, Decimal('10'))])
    True
    >>> len(time_series)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.product.id, r.date, r.number, r.expense)
    ...         for r in time_series) == sorted(
    ...     [(product1.id, purchase1_ts_date, 1, Decimal('20')),
    ...     (product2.id, purchase1_ts_date, 1, Decimal('10'))])
    True
