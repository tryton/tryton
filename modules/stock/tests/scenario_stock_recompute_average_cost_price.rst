==================================
Stock Recompute Average Cost Price
==================================

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
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> product, = template.products
    >>> product.cost_price = Decimal('80')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

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
    ...     from_location=storage_loc,
    ...     to_location=customer_loc,
    ...     unit_price=Decimal('300'),
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=2,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('120'),
    ...     effective_date=today - dt.timedelta(days=1)).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=3,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('100'),
    ...     effective_date=today).click('do')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('105.0000'), Decimal('120.0000'), Decimal('100.0000'), Decimal('100.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('105.0000')

Recompute cost price::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.execute('recompute')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('105.0000'), Decimal('120.0000'), Decimal('120.0000'), Decimal('100.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('105.0000')

Recompute cost price from a date::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.form.from_ = today - dt.timedelta(days=1)
    >>> recompute.execute('recompute')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('105.0000'), Decimal('120.0000'), Decimal('120.0000'), Decimal('100.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('105.0000')

Update unit price of a move::

    >>> move, = StockMove.find([
    ...         ('from_location', '=', supplier_loc.id),
    ...         ('effective_date', '=', today - dt.timedelta(days=1)),
    ...         ])
    >>> bool(move.unit_price_updated)
    False
    >>> move.unit_price = Decimal('130')
    >>> move.save()
    >>> bool(move.unit_price_updated)
    True

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.form.from_ = move.effective_date + dt.timedelta(days=1)
    >>> recompute.execute('recompute')
    >>> move.reload()
    >>> bool(move.unit_price_updated)
    True

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.form.from_ == move.effective_date
    True
    >>> recompute.execute('recompute')
    >>> move.reload()
    >>> bool(move.unit_price_updated)
    False
    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('107.5000'), Decimal('130.0000'), Decimal('130.0000'), Decimal('100.0000')]

Launch cron task::

    >>> move.unit_price = Decimal('120')
    >>> move.save()

    >>> Cron = Model.get('ir.cron')
    >>> Company = Model.get('company.company')
    >>> cron_recompute, = Cron.find([
    ...     ('method', '=', 'product.product|recompute_cost_price_from_moves'),
    ...     ])
    >>> cron_recompute.companies.append(Company(company.id))
    >>> cron_recompute.click('run_once')

    >>> move.reload()
    >>> bool(move.unit_price_updated)
    False
    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('105.0000'), Decimal('120.0000'), Decimal('120.0000'), Decimal('100.0000')]
