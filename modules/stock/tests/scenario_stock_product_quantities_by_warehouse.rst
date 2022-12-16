=====================================
Stock Product Quantities by Warehouse
=====================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond import backend
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)
    >>> tomorrow = today + relativedelta(days=1)

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
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Fill warehouse::

   >>> Move = Model.get('stock.move')
   >>> move = Move()
   >>> move.product = product
   >>> move.from_location = supplier_loc
   >>> move.to_location = storage_loc
   >>> move.uom = unit
   >>> move.quantity = 10
   >>> move.effective_date = yesterday
   >>> move.unit_price = Decimal('10')
   >>> move.click('do')

Forecast some moves::

   >>> move = Move()
   >>> move.product = product
   >>> move.from_location = storage_loc
   >>> move.to_location = customer_loc
   >>> move.uom = unit
   >>> move.quantity = 6
   >>> move.planned_date = tomorrow
   >>> move.unit_price = Decimal('20')
   >>> move.save()

   >>> move = Move()
   >>> move.product = product
   >>> move.from_location = supplier_loc
   >>> move.to_location = storage_loc
   >>> move.uom = unit
   >>> move.quantity = 5
   >>> move.planned_date = tomorrow
   >>> move.unit_price = Decimal('10')
   >>> move.save()

   >>> move = Move()
   >>> move.product = product
   >>> move.from_location = storage_loc
   >>> move.to_location = customer_loc
   >>> move.uom = unit
   >>> move.quantity = 3
   >>> move.planned_date = tomorrow
   >>> move.unit_price = Decimal('20')
   >>> move.save()


Check Product Quantities by Warehouse::

   >>> ProductQuantitiesByWarehouse = Model.get('stock.product_quantities_warehouse')
   >>> with config.set_context(
   ...      product_template=template.id, warehouse=warehouse_loc.id):
   ...   records = ProductQuantitiesByWarehouse.find([])
   >>> len(records)
   3
   >>> [(r.date, r.quantity) for r in records] == [
   ...      (yesterday, 10), (today, 10), (tomorrow, 6)]
   True

Check Product Quantities by Warehouse Moves::

    >>> ProductQuantitiesByWarehouseMove = Model.get(
    ...     'stock.product_quantities_warehouse.move')
    >>> with config.set_context(
    ...      product_template=template.id, warehouse=warehouse_loc.id):
    ...   records = ProductQuantitiesByWarehouseMove.find([])
    >>> len(records)
    4
    >>> if backend.name != 'sqlite':
    ...     [(r.date, r.cumulative_quantity_start, r.quantity, r.cumulative_quantity_end)
    ...         for r in records] == [
    ...     (yesterday, 0, 10, 10),
    ...     (tomorrow, 10, -6, 4),
    ...     (tomorrow, 4, 5, 9),
    ...     (tomorrow, 9, -3, 6)]
    ... else:
    ...     [(r.date, r.cumulative_quantity_start, r.quantity, r.cumulative_quantity_end)
    ...         for r in records] == [
    ...     (yesterday, 0, 10, 0),
    ...     (tomorrow, 10, -6, 10),
    ...     (tomorrow, 10, 5, 10),
    ...     (tomorrow, 10, -3, 10)]
    True
