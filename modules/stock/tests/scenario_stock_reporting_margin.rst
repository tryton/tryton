===============================
Stock Reporting Margin Scenario
===============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('40')
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('20')
    >>> product.save()
    >>> template2, = template.duplicate()
    >>> product2, = template2.products

    >>> Category = Model.get('product.category')
    >>> category_root = Category(name="Root")
    >>> category_root.save()
    >>> category1 = Category(name="Child1", parent=category_root)
    >>> category1.save()
    >>> category2 = Category(name="Child2", parent=category_root)
    >>> category2.save()

    >>> template.categories.append(Category(category1.id))
    >>> template.save()
    >>> template2.categories.append(Category(category2.id))
    >>> template2.save()


Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Create some moves::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.quantity = 8
    >>> move.unit_price = Decimal('20')
    >>> move.effective_date = yesterday
    >>> move.click('do')

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.quantity = 2
    >>> move.unit_price = Decimal('40')
    >>> move.effective_date = yesterday
    >>> move.click('do')

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.quantity = 4
    >>> move.unit_price = Decimal('30')
    >>> move.effective_date = today
    >>> move.click('do')

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = customer_loc
    >>> move.to_location = storage_loc
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('30')
    >>> move.effective_date = today
    >>> move.click('do')

    >>> move = Move()
    >>> move.product = product2
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.quantity = 2
    >>> move.unit_price = Decimal('50')
    >>> move.effective_date = today
    >>> move.click('do')

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = storage_loc
    >>> move.to_location = lost_loc
    >>> move.quantity = 1
    >>> move.effective_date = today
    >>> move.click('do')

Check reporting margin per product::

    >>> MarginProduct = Model.get('stock.reporting.margin.product')
    >>> MarginProductTimeseries = Model.get(
    ...     'stock.reporting.margin.product.time_series')
    >>> context = {
    ...     'from_date': yesterday,
    ...     'to_date': today,
    ...     'period': 'day',
    ...     }
    >>> with config.set_context(context=context):
    ...     reports = MarginProduct.find([])
    ...     time_series = MarginProductTimeseries.find([])
    >>> len(reports)
    2
    >>> report, = [r for r in reports if r.product == product]
    >>> (report.quantity, report.cost, report.revenue,
    ...     report.profit, report.margin) == (
    ...     5, Decimal('100.00'), Decimal('170.00'),
    ...     Decimal('70.00'), Decimal('0.4118'))
    True
    >>> len(time_series)
    3
    >>> with config.set_context(context=context):
    ...     sorted((
    ...             r.product.id, str(r.date), r.quantity, r.cost, r.revenue,
    ...             r.profit, r.margin)
    ...         for r in time_series) == sorted([
    ...     (product.id, str(yesterday), 2, Decimal('40.00'), Decimal('80.00'),
    ...         Decimal('40.00'), Decimal('0.5000')),
    ...     (product.id, str(today), 3, Decimal('60.00'), Decimal('90.00'),
    ...         Decimal('30.00'), Decimal('0.3333')),
    ...     (product2.id, str(today), 2, Decimal('40.00'), Decimal('100.00'),
    ...         Decimal('60.00'), Decimal('0.6000'))])
    True

Check reporting margin per categories::

    >>> MarginCategory = Model.get('stock.reporting.margin.category')
    >>> MarginCategoryTimeseries = Model.get(
    ...     'stock.reporting.margin.category.time_series')
    >>> MarginCategoryTree = Model.get(
    ...     'stock.reporting.margin.category.tree')
    >>> with config.set_context(context=context):
    ...     reports = MarginCategory.find([])
    ...     time_series = MarginCategoryTimeseries.find([])
    ...     tree = MarginCategoryTree.find([])
    >>> len(reports)
    2
    >>> with config.set_context(context=context):
    ...     sorted((r.category.id, r.cost, r.revenue, r.profit, r.margin)
    ...         for r in reports) == sorted([
    ...     (category1.id, Decimal('100.00'), Decimal('170.00'),
    ...         Decimal('70.00'), Decimal('0.4118')),
    ...     (category2.id, Decimal('40.00'), Decimal('100.00'),
    ...         Decimal('60.00'), Decimal('0.6000'))])
    True
    >>> len(time_series)
    3
    >>> with config.set_context(context=context):
    ...     sorted((r.category.id, str(r.date), r.cost, r.revenue, r.profit, r.margin)
    ...         for r in time_series) == sorted([
    ...     (category1.id, str(yesterday), Decimal('40.00'), Decimal('80.00'),
    ...         Decimal('40.00'), Decimal('0.5000')),
    ...     (category1.id, str(today), Decimal('60.00'), Decimal('90.00'),
    ...         Decimal('30.00'), Decimal('0.3333')),
    ...     (category2.id, str(today), Decimal('40.00'), Decimal('100.00'),
    ...         Decimal('60.00'), Decimal('0.6000'))])
    True
    >>> len(tree)
    3
    >>> with config.set_context(context=context):
    ...     sorted((r.name, r.cost, r.revenue, r.profit, r.margin)
    ...         for r in tree) == sorted([
    ...     ("Root", Decimal('140.00'), Decimal('270.00'),
    ...         Decimal('130.00'), Decimal('0.4815')),
    ...     ("Child1", Decimal('100.00'), Decimal('170.00'),
    ...         Decimal('70.00'), Decimal('0.4118')),
    ...     ('Child2', Decimal('40.00'), Decimal('100.00'),
    ...         Decimal('60.00'), Decimal('0.6000'))])
    True

Check reporting margin including lost::

    >>> context['include_lost'] = True

    >>> with config.set_context(context=context):
    ...     reports = MarginProduct.find([])
    >>> len(reports)
    2
    >>> report, = [r for r in reports if r.product == product]
    >>> (report.quantity, report.cost, report.revenue,
    ...     report.profit, report.margin) == (
    ...     6, Decimal('120.00'), Decimal('170.00'),
    ...     Decimal('50.00'), Decimal('0.2941'))
    True
