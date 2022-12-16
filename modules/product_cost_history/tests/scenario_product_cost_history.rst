====================
Product Cost History
====================

Imports::

    >>> import datetime as dt
    >>> import time
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = dt.date.today()
    >>> now = dt.datetime.now()

Activate modules::

    >>> config = activate_modules('product_cost_history')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('200.0000')
    >>> product, = template.products
    >>> product.cost_price = Decimal('100.0000')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Cost history is empty::

    >>> ProductCostHistory = Model.get('product.product.cost_history')
    >>> ProductCostHistory.find([])
    []

Create some moves at different dates and with different cost::

    >>> StockMove = Model.get('stock.move')
    >>> product.cost_price = Decimal('100.0000')
    >>> product.save()
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('100.0000'),
    ...     effective_date=today - dt.timedelta(days=2)).click('do')
    >>> modify_cost_price = Wizard('product.modify_cost_price', [product])
    >>> modify_cost_price.form.cost_price = '90.0000'
    >>> modify_cost_price.execute('modify')
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('90.0000'),
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> modify_cost_price = Wizard('product.modify_cost_price', [product])
    >>> modify_cost_price.form.cost_price = '120.0000'
    >>> modify_cost_price.execute('modify')
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('120.0000'),
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> modify_cost_price = Wizard('product.modify_cost_price', [product])
    >>> modify_cost_price.form.cost_price = '110.0000'
    >>> modify_cost_price.execute('modify')
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('110.0000'),
    ...     effective_date=today).click('do')


Check cost history::

    >>> order = [('date', 'ASC')]
    >>> [c.cost_price for c in ProductCostHistory.find([], order=order)] == [
    ...     Decimal('100.0000'), Decimal('120.0000'), Decimal('110.0000')]
    True
    >>> [c.date for c in ProductCostHistory.find([], order=order)] == [
    ...     today - dt.timedelta(days=2),
    ...     today - dt.timedelta(days=1),
    ...     today]
    True

Check cost price history on product::

    >>> product.reload()
    >>> product.cost_price
    Decimal('110.0000')

    >>> with config.set_context(_datetime=now - dt.timedelta(days=3)):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('0')

    >>> with config.set_context(_datetime=now - dt.timedelta(days=2)):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('100.0000')

    >>> with config.set_context(_datetime=now - dt.timedelta(days=1)):
    ...     product = Product(product.id)
    >>> product.cost_price
    Decimal('120.0000')


Create service::

    >>> template = ProductTemplate()
    >>> template.name = 'Service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('50.0000')
    >>> service, = template.products
    >>> service.cost_price = Decimal('30.0000')
    >>> template.save()
    >>> sevice, = template.products

Update cost price::

    >>> service.cost_price += 5
    >>> service.save()

Check cost history::

    >>> history, = ProductCostHistory.find([('product', '=', service.id)])
    >>> history.cost_price == Decimal('35.0000')
    True
