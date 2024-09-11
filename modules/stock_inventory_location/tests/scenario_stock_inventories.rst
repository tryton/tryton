==========================
Stock Inventories Scenario
==========================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_inventory_location', create_company)

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> storage_loc2, = storage_loc.duplicate()

Create inventories::

    >>> create = Wizard('stock.inventory.create')
    >>> create.form.empty_quantity = 'keep'
    >>> create.form.locations.extend(Location.find([('code', '=', 'STO')]))
    >>> create.execute('create_')

    >>> inventories, = create.actions
    >>> len(inventories)
    2
    >>> assertEqual({i.location for i in inventories}, {storage_loc, storage_loc2})
    >>> inventories[0].empty_quantity
    'keep'
