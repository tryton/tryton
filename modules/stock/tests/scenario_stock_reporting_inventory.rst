==================================
Stock Reporting Inventory Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from unittest.mock import patch

    >>> from proteus import Model
    >>> from trytond.ir.date import Date
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> period_close = globals().get('period_close', False)
    >>> product_type = globals().get('product_type', 'product.template')

Patch today::

    >>> mock = patch.object(Date, 'today', return_value=dt.date(2025, 1, 15))
    >>> _ = mock.start()

Activate modules::

    >>> config = activate_modules('stock', create_company)

    >>> Inventory = Model.get('stock.reporting.inventory')
    >>> InventoryMove = Model.get('stock.reporting.inventory.move')
    >>> InventoryDaily = Model.get('stock.reporting.inventory.daily')
    >>> InventoryTurnover = Model.get('stock.reporting.inventory.turnover')
    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> Period = Model.get('stock.period')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')

Get currency::

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

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Fill warehouse::

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.quantity = 10
    >>> move.effective_date = dt.date(2025, 1, 1)
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = currency
    >>> move.click('do')
    >>> move.state
    'done'

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.effective_date = dt.date(2025, 1, 1)
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = currency
    >>> move.click('do')
    >>> move.state
    'done'

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit = unit
    >>> move.quantity = 2
    >>> move.effective_date = dt.date(2025, 1, 10)
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = currency
    >>> move.click('do')
    >>> move.state
    'done'

Forecast some moves::

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.quantity = 10
    >>> move.effective_date = dt.date(2025, 1, 5)
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = currency
    >>> move.save()
    >>> move.state
    'draft'

    >>> move = Move()
    >>> move.product = product
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit = unit
    >>> move.quantity = 3
    >>> move.planned_date = dt.date(2025, 1, 20)
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = currency
    >>> move.save()
    >>> move.state
    'draft'

Close period::

    >>> period = Period(date=dt.date(2025, 1, 5))
    >>> if period_close:
    ...     period.click('close')


Check inventory::

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         product_type=product_type,
    ...         date=dt.date(2024, 1, 1)):
    ...     Inventory.find([])
    []

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         product_type=product_type,
    ...         date=dt.date(2025, 1, 1)):
    ...     inventory, = Inventory.find([])
    >>> inventory.quantity
    9.0
    >>> assertEqual(inventory.product.__class__.__name__, product_type)

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         product_type=product_type,
    ...         date=dt.date(2025, 1, 15)):
    ...     inventory, = Inventory.find([])
    >>> inventory.quantity
    7.0

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         product_type=product_type,
    ...         date=dt.date(2025, 1, 20)):
    ...     inventory, = Inventory.find([])
    >>> inventory.quantity
    4.0

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         product_type=product_type):
    ...     inventory_moves = InventoryMove.find([])
    ...     inventories_daily = InventoryDaily.find([])

    >>> [i.quantity for i in inventory_moves]
    [4.0, 7.0, 9.0, 10.0]
    >>> [(i.input_quantity, i.output_quantity) for i in inventory_moves]
    [(None, 3.0), (None, 2.0), (None, 1.0), (10.0, None)]

    >>> [i.quantity for i in inventories_daily]
    [4.0, 7.0, 9.0]
    >>> [(i.input_quantity, i.output_quantity) for i in inventories_daily]
    [(None, 3.0), (None, 2.0), (10.0, 1.0)]

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         from_date=dt.date(2025, 1, 15),
    ...         to_date=dt.date(2025, 1, 29),
    ...         product_type=product_type):
    ...     inventory_moves = InventoryMove.find([])
    ...     inventories_daily = InventoryDaily.find([])

    >>> [i.quantity for i in inventory_moves]
    [4.0, 7.0]
    >>> [(i.input_quantity, i.output_quantity) for i in inventory_moves]
    [(None, 3.0), (None, None)]

    >>> [i.quantity for i in inventories_daily]
    [4.0, 7.0]
    >>> [(i.input_quantity, i.output_quantity) for i in inventories_daily]
    [(None, 3.0), (None, None)]

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         from_date=dt.date(2025, 1, 10),
    ...         to_date=dt.date(2025, 1, 29),
    ...         product_type=product_type):
    ...     inventory_moves = InventoryMove.find([])
    ...     inventories_daily = InventoryDaily.find([])

    >>> assertEqual(
    ...     [i.quantity for i in inventory_moves],
    ...     [4.0, 7.0] if period_close else [4.0, 7.0, 9.0])
    >>> assertEqual(
    ...     [(i.input_quantity, i.output_quantity) for i in inventory_moves],
    ...     [(None, 3.0), (None, 2.0)] if period_close
    ...     else [(None, 3.0), (None, 2.0), (None, None)])

    >>> [i.quantity for i in inventories_daily]
    [4.0, 7.0]
    >>> [(i.input_quantity, i.output_quantity) for i in inventories_daily]
    [(None, 3.0), (None, 2.0)]

Check Inventory turnover::

    >>> with config.set_context(
    ...         location=warehouse_loc.id,
    ...         from_date=dt.date(2025, 1, 10),
    ...         to_date=dt.date(2025, 1, 29),
    ...         product_type=product_type):
    ...     turnover, = InventoryTurnover.find([])

    >>> turnover.output_quantity
    0.25
    >>> turnover.average_quantity
    5.5
    >>> turnover.turnover
    0.045
    >>> assertEqual(turnover.product.__class__.__name__, product_type)
