======================================
Product Cost FIFO Recompute Cost Price
======================================

Imports::

    >>> import datetime as dt
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('product_cost_fifo')

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
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'fifo'
    >>> product, = template.products
    >>> product.cost_price = Decimal('80')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> lost_found, = Location.find([('name', '=', "Lost and Found")])

Create some moves::

    >>> StockMove = Model.get('stock.move')
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('100'),
    ...     effective_date=today - dt.timedelta(days=2)).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=2,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('120'),
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=lost_found,
    ...     to_location=storage_loc,
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=2,
    ...     from_location=storage_loc,
    ...     to_location=customer_loc,
    ...     unit_price=Decimal('300'),
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=3,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('100'),
    ...     effective_date=today).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=2,
    ...     from_location=storage_loc,
    ...     to_location=customer_loc,
    ...     unit_price=Decimal('300'),
    ...     effective_date=today).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=1,
    ...     from_location=storage_loc,
    ...     to_location=lost_found,
    ...     effective_date=today).click('do')


    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('100.0000'), Decimal('116.6666'), Decimal('106.6666'), Decimal('110.0000'), Decimal('113.3333'), Decimal('113.3333'), Decimal('100.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('99.9998')

Recompute cost price::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.execute('recompute')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('111.1111'), Decimal('111.1111'), Decimal('106.6666'), Decimal('110.0000'), Decimal('113.3333'), Decimal('113.3333'), Decimal('100.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('100.0000')

Recompute cost price from a date::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.form.from_ = today - dt.timedelta(days=1)
    >>> recompute.execute('recompute')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('111.1111'), Decimal('111.1111'), Decimal('106.6666'), Decimal('110.0000'), Decimal('113.3333'), Decimal('113.3333'), Decimal('100.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('100.0000')
