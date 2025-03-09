============================
Stock Location Move Scenario
============================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(1)

Activate modules::

    >>> config = activate_modules('stock_location_move', create_company)

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> storage1 = Location(name="Storage 1", parent=storage_loc)
    >>> storage1.save()
    >>> storage2 = Location(name="Storage 2", parent=storage_loc)
    >>> storage2.save()
    >>> pallet = Location(name="Pallet", parent=storage1, movable=True)
    >>> pallet.save()

Move pallet from storage1 to storage2::

    >>> Shipment = Model.get('stock.shipment.internal')
    >>> shipment = Shipment()
    >>> shipment.from_location = storage1
    >>> shipment.to_location = storage2
    >>> shipment.locations.append(Location(pallet.id))
    >>> shipment.click('wait')

    >>> shipment.click('assign_try')
    >>> shipment.state
    'assigned'
    >>> pallet.reload()
    >>> assertEqual(pallet.assigned_by, shipment)
    >>> assertEqual(pallet.parent, storage1)

    >>> shipment.click('do')
    >>> shipment.state
    'done'
    >>> pallet.reload()
    >>> pallet.assigned_by
    >>> assertEqual(pallet.parent, storage2)

Assign pallet from wrong location::

    >>> shipment = Shipment()
    >>> shipment.from_location = storage1
    >>> shipment.to_location = storage2
    >>> shipment.locations.append(Location(pallet.id))
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    Traceback (most recent call last):
        ...
    DomainValidationError: ...

Concurrently move pallet::

    >>> shipment1 = Shipment()
    >>> shipment1.from_location = storage2
    >>> shipment1.to_location = storage1
    >>> shipment1.locations.append(Location(pallet.id))
    >>> shipment1.click('wait')

    >>> shipment2 = Shipment()
    >>> shipment2.from_location = storage2
    >>> shipment2.to_location = storage1
    >>> shipment2.locations.append(Location(pallet.id))
    >>> shipment2.click('wait')

    >>> shipment1.click('assign_try')
    >>> shipment1.state
    'assigned'
    >>> shipment2.click('assign_try')
    Traceback (most recent call last):
        ...
    AssignError: ...

    >>> shipment1.click('do')

Add lead time between warehouses::

    >>> warehouse1 = storage_loc.warehouse
    >>> warehouse2, = warehouse1.duplicate()

    >>> LeadTime = Model.get('stock.location.lead_time')
    >>> lead_time = LeadTime()
    >>> lead_time.warehouse_from = warehouse1
    >>> lead_time.warehouse_to = warehouse2
    >>> lead_time.lead_time = dt.timedelta(1)
    >>> lead_time.save()

Move pallet from storage1 to storage2 with lead_time::

    >>> Shipment = Model.get('stock.shipment.internal')
    >>> shipment = Shipment()
    >>> shipment.planned_date = tomorrow
    >>> shipment.from_location = warehouse1.storage_location
    >>> shipment.to_location = warehouse2.storage_location
    >>> shipment.locations.append(Location(pallet.id))
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    >>> shipment.click('pack')
    >>> shipment.click('ship')
    >>> shipment.state
    'shipped'
    >>> pallet.reload()
    >>> assertEqual(pallet.parent, shipment.transit_location)

    >>> shipment.click('do')
    >>> pallet.reload()
    >>> assertEqual(pallet.parent, warehouse2.storage_location)
