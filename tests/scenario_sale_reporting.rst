=======================
Sale Reporting Scenario
=======================

Imports::

    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Install sale::

    >>> config = activate_modules('sale')

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
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create countries::

    >>> Country = Model.get('country.country')
    >>> Subdivision = Model.get('country.subdivision')
    >>> country_us = Country(
    ...     name="United States", code="US", code3="USA", code_numeric="840")
    >>> country_us.save()
    >>> california = Subdivision(
    ...     name="California", code="US-CA", type='state', country=country_us)
    >>> california.save()
    >>> new_york = Subdivision(
    ...     name="New York", code="US-NY", type='state', country=country_us)
    >>> new_york.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer1 = Party(name='Customer1')
    >>> address, = customer1.addresses
    >>> address.country = country_us
    >>> address.subdivision = california
    >>> customer1.save()
    >>> customer2 = Party(name='Customer2')
    >>> address, = customer2.addresses
    >>> address.country = country_us
    >>> address.subdivision = new_york
    >>> customer2.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Category = Model.get('product.category')

    >>> template1 = ProductTemplate()
    >>> template1.name = "Product1"
    >>> template1.default_uom = unit
    >>> template1.type = 'service'
    >>> template1.salable = True
    >>> template1.list_price = Decimal('10')
    >>> template1.account_revenue = revenue
    >>> template1.save()
    >>> product1, = template1.products

    >>> template2, = template1.duplicate(default={'name': "Product2"})
    >>> product2, = template2.products

    >>> category_root1 = Category(name="Root1")
    >>> category_root1.save()
    >>> category_child1 = Category(name="Child1", parent=category_root1)
    >>> category_child1.save()
    >>> category_child2 = Category(name="Child2", parent=category_root1)
    >>> category_child2.save()
    >>> category_root2 = Category(name="Root2")
    >>> category_root2.save()

    >>> template1.categories.append(Category(category_child1.id))
    >>> template1.categories.append(Category(category_root2.id))
    >>> template1.save()
    >>> template2.categories.append(Category(category_child2.id))
    >>> template2.save()

Create sales::

    >>> Sale = Model.get('sale.sale')

    >>> sale1 = Sale()
    >>> sale1.party = customer1
    >>> sale1.sale_date = fiscalyear.start_date
    >>> line = sale1.lines.new()
    >>> line.product = product1
    >>> line.quantity = 2
    >>> line = sale1.lines.new()
    >>> line.product = product2
    >>> line.quantity = 1
    >>> sale1.click('quote')
    >>> sale1.click('confirm')

    >>> sale2 = Sale()
    >>> sale2.party = customer2
    >>> sale2.sale_date = fiscalyear.start_date + relativedelta(months=1)
    >>> line = sale2.lines.new()
    >>> line.product = product1
    >>> line.quantity = 1
    >>> sale2.click('quote')
    >>> sale2.click('confirm')

Check sale reporting per customer::

    >>> Customer = Model.get('sale.reporting.customer')
    >>> CustomerTimeseries = Model.get('sale.reporting.customer.time_series')
    >>> context = dict(
    ...         from_date=fiscalyear.start_date,
    ...         to_date=fiscalyear.end_date,
    ...         period='month')
    >>> with config.set_context(context=context):
    ...     reports = Customer.find([])
    ...     time_series = CustomerTimeseries.find([])
    >>> len(reports)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.customer.id, r.number, r.revenue) for r in reports) == \
    ...     sorted([(customer1.id, 1, Decimal('30')),
    ...             (customer2.id, 1, Decimal('10'))])
    True
    >>> len(time_series)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.customer.id, str(r.date), r.number, r.revenue)
    ...         for r in time_series) == sorted(
    ...     [(customer1.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('30')),
    ...     (customer2.id, str(sale2.sale_date.replace(day=1)), 1, Decimal('10'))])
    True

Check sale reporting per product::

    >>> Product = Model.get('sale.reporting.product')
    >>> ProductTimeseries = Model.get('sale.reporting.product.time_series')
    >>> with config.set_context(context=context):
    ...     reports = Product.find([])
    ...     time_series = ProductTimeseries.find([])
    >>> len(reports)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.product.id, r.number, r.revenue) for r in reports) == \
    ...     sorted([(product1.id, 2, Decimal('30')),
    ...         (product2.id, 1, Decimal('10'))])
    True
    >>> len(time_series)
    3
    >>> with config.set_context(context=context):
    ...     sorted((r.product.id, str(r.date), r.number, r.revenue)
    ...         for r in time_series) == sorted(
    ...     [(product1.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('20')),
    ...     (product2.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('10')),
    ...     (product1.id, str(sale2.sale_date.replace(day=1)), 1, Decimal('10'))])
    True

Check sale reporting per categories::

    >>> Category = Model.get('sale.reporting.category')
    >>> CategoryTimeseries = Model.get('sale.reporting.category.time_series')
    >>> CategoryTree = Model.get('sale.reporting.category.tree')
    >>> with config.set_context(context=context):
    ...     reports = Category.find([])
    ...     time_series = CategoryTimeseries.find([])
    ...     tree = CategoryTree.find([])
    >>> len(reports)
    3
    >>> with config.set_context(context=context):
    ...     sorted((r.category.id, r.number, r.revenue) for r in reports) == \
    ...     sorted([(category_child1.id, 2, Decimal('30')),
    ...         (category_root2.id, 2, Decimal('30')),
    ...         (category_child2.id, 1, Decimal('10'))])
    True
    >>> len(time_series)
    5
    >>> with config.set_context(context=context):
    ...     sorted((r.category.id, str(r.date), r.number, r.revenue)
    ...         for r in time_series) == sorted(
    ...     [(category_child1.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('20')),
    ...     (category_root2.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('20')),
    ...     (category_child2.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('10')),
    ...     (category_child1.id, str(sale2.sale_date.replace(day=1)), 1, Decimal('10')),
    ...     (category_root2.id, str(sale2.sale_date.replace(day=1)), 1, Decimal('10'))])
    True
    >>> len(tree)
    4
    >>> with config.set_context(context=context):
    ...     sorted((r.name, r.revenue) for r in tree) == sorted([
    ...         (u'Root1', Decimal('40')),
    ...         (u'Child1', Decimal('30')),
    ...         (u'Child2', Decimal('10')),
    ...         (u'Root2', Decimal('30'))])
    True

Check sale reporting per regions::

    >>> Region = Model.get('sale.reporting.region')
    >>> CountryTimeseries = Model.get('sale.reporting.country.time_series')
    >>> SubdivisionTimeseries = Model.get(
    ...     'sale.reporting.country.subdivision.time_series')
    >>> with config.set_context(context=context):
    ...     reports = Region.find([])
    ...     country_time_series = CountryTimeseries.find([])
    ...     subdivision_time_series = SubdivisionTimeseries.find([])
    >>> len(reports)
    3
    >>> with config.set_context(context=context):
    ...     sorted((r.region, r.number, r.revenue) for r in reports) == \
    ...     sorted([('United States', 2, Decimal('40')),
    ...         ('California', 1, Decimal('30')),
    ...         ('New York', 1, Decimal('10'))])
    True
    >>> len(country_time_series)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.country.id, str(r.date), r.number, r.revenue)
    ...         for r in country_time_series) == sorted(
    ...     [(country_us.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('30')),
    ...     (country_us.id, str(sale2.sale_date.replace(day=1)), 1, Decimal('10'))])
    True
    >>> len(subdivision_time_series)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.subdivision.id, str(r.date), r.number, r.revenue)
    ...         for r in subdivision_time_series) == sorted(
    ...     [(california.id, str(sale1.sale_date.replace(day=1)), 1, Decimal('30')),
    ...     (new_york.id, str(sale2.sale_date.replace(day=1)), 1, Decimal('10'))])
    True
