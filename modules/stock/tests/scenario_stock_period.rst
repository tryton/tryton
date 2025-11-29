=====================
Stock Period Scenario
=====================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> Period = Model.get('stock.period')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')

    >>> currency = get_currency()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create a period::

    >>> period = Period(date=yesterday)
    >>> period.save()

Close the period::

    >>> period.click('close')
    >>> period.state
    'closed'

Try to create a move::

    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.planned_date = yesterday
    >>> move.unit_price = Decimal('42.0000')
    >>> move.currency = currency
    >>> move.save()
    Traceback (most recent call last):
        ...
    AccessError: ...

Reopen the period::

    >>> period.click('draft')
    >>> period.state
    'draft'

Close the period with draft move::

    >>> move.save()
    >>> period.click('close')
    >>> period.state
    'closed'

Reopen the period::

    >>> period.click('draft')
    >>> period.state
    'draft'

Create an assigned move::

    >>> Move.write([move], {'state': 'assigned'}, config._context)
    >>> move.state
    'assigned'

Close the period with assigned move::

    >>> period.click('close')
    Traceback (most recent call last):
        ...
    PeriodCloseError: ...

Try to close a period on today::

    >>> period = Period(date=today)
    >>> period.click('close')
    Traceback (most recent call last):
        ...
    PeriodCloseError: ...
