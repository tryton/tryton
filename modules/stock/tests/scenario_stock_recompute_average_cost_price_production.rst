=============================================
Stock Recompute Average Cost Price Production
=============================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock')

    >>> Location = Model.get('stock.location')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> StockMove = Model.get('stock.move')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('50.0000')
    >>> template.cost_price_method = 'average'
    >>> product, = template.products
    >>> product.cost_price = Decimal('40.0000')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> production_loc = Location(name="Production", type='production')
    >>> production_loc.save()

Consume product for production and reverse some::

    >>> StockMove(
    ...     product=product,
    ...     quantity=10,
    ...     from_location=storage_loc,
    ...     to_location=production_loc,
    ...     effective_date=today).click('do')
    >>> StockMove(
    ...     product=product,
    ...     quantity=2,
    ...     from_location=production_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('40.0000'),
    ...     effective_date=today).click('do')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('40.0000'), Decimal('40.0000')]

Recompute cost price::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.execute('recompute')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('0.0000'), Decimal('0.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('0.0000')

Receive product yesterday at new cost::

    >>> StockMove(
    ...     product=product,
    ...     quantity=16,
    ...     from_location=supplier_loc,
    ...     to_location=storage_loc,
    ...     unit_price=Decimal('20.0000'),
    ...     effective_date=yesterday).click('do')

Recompute cost price::

    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.execute('recompute')

    >>> [m.cost_price for m in StockMove.find([])]
    [Decimal('20.0000'), Decimal('20.0000'), Decimal('20.0000')]

    >>> product.reload()
    >>> product.cost_price
    Decimal('20.0000')
