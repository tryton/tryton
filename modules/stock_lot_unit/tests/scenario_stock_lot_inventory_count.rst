=======================================
Stock Lot Unit Inventory Count Scenario
=======================================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_lot_unit', create_company)
    >>> config.skip_warning = True

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')

Get stock location::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create product and lot::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.lot_required = ['storage']
    >>> template.save()
    >>> product, = template.products

    >>> lot = Lot(number="0001", product=product, unit=unit)
    >>> lot.save()

Create an inventory::

    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.empty_quantity = 'keep'
    >>> inventory.save()

Count inventory::

    >>> count = inventory.click('do_count')

    >>> count.form.search = lot
    >>> count.execute('quantity')
    >>> assertEqual(count.form.product, product)
    >>> assertEqual(count.form.lot, lot)
    >>> count.form.quantity
    1.0
    >>> count.form.total_quantity
    1.0
    >>> count.execute('add')
    >>> count.execute('end')

Check inventory::

    >>> line, = inventory.lines
    >>> assertEqual(line.product, product)
    >>> assertEqual(line.lot, lot)
    >>> line.quantity
    1.0
