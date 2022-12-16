=============================
Stock Move In Future Scenario
=============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> today = datetime.date.today()
    >>> tomorrow = today + relativedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock')

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
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('1')
    >>> product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

A warning is raised when doing a move in the future::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.currency = company.currency
    >>> move.effective_date = tomorrow
    >>> move.quantity = 2
    >>> move.unit_price = Decimal('1')
    >>> move.save()
    >>> move.click('do')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    MoveFutureWarning: ...

But it can be done for today::

    >>> move.effective_date = today
    >>> move.click('do')
    >>> move.state
    'done'
