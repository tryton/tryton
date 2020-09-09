==========================
Stock Inventories Scenario
==========================

Imports::

    >>> import datetime as dt
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('stock_inventory_location')

Create company::

    >>> _ = create_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> storage_loc2, = storage_loc.duplicate()

Create inventories::

    >>> create = Wizard('stock.inventory.create')
    >>> create.form.date = today
    >>> create.form.locations.extend(Location.find([('code', '=', 'STO')]))
    >>> create.execute('create_')

    >>> inventories, = create.actions
    >>> len(inventories)
    2
    >>> {i.location for i in inventories} == {storage_loc, storage_loc2}
    True
