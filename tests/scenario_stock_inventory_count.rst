==============================
Stock Inventory Count Scenario
==============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create products::

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

    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> template2 = ProductTemplate()
    >>> template2.name = 'Product'
    >>> template2.default_uom = kg
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal('140')
    >>> template2.cost_price_method = 'average'
    >>> product2, = template2.products
    >>> product2.cost_price = Decimal('60')
    >>> template2.save()
    >>> product2, = template2.products

Create an inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> inventory.save()

Count inventory::

    >>> _ = inventory.click('count')
    >>> count = Wizard('stock.inventory.count', [inventory])

    >>> count.form.search = product

    >>> count.execute('quantity')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    InventoryCountWarning: ...

    >>> Model.get('res.user.warning')(user=config.user,
    ...     name='stock.inventory,%s.product.product,%s.count_create' % (
    ...     inventory.id, product.id)).save()
    >>> count.execute('quantity')
    >>> count.form.quantity_added
    1
    >>> count.form.total_quantity
    1
    >>> count.execute('add')

    >>> count.form.search = product
    >>> count.execute('quantity')
    >>> count.form.total_quantity
    2.0
    >>> count.execute('add')

    >>> count.form.search = product2
    >>> Model.get('res.user.warning')(user=config.user,
    ...     name='stock.inventory,%s.product.product,%s.count_create' % (
    ...     inventory.id, product2.id)).save()
    >>> count.execute('quantity')
    >>> count.form.quantity_added
    >>> count.form.total_quantity
    >>> count.form.quantity_added = 10
    >>> count.form.total_quantity
    10.0
    >>> count.execute('add')

    >>> count.execute('end')

Check inventory::

    >>> len(inventory.lines)
    2
    >>> line1, = [l for l in inventory.lines if l.product == product]
    >>> line1.quantity
    2.0
    >>> line2, = [l for l in inventory.lines if l.product == product2]
    >>> line2.quantity
    10.0
