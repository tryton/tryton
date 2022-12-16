============================
Stock Location Move Scenario
============================

Imports::

    >>> import datetime

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()
    >>> tomorrow = today + datetime.timedelta(1)

Activate modules::

    >>> config = activate_modules('stock_location_move')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    True
    >>> shipment.state
    'assigned'
    >>> pallet.reload()
    >>> pallet.assigned_by == shipment
    True
    >>> pallet.parent == storage1
    True

    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> pallet.reload()
    >>> pallet.assigned_by
    >>> pallet.parent == storage2
    True

Assign pallet from wrong location::

    >>> shipment = Shipment()
    >>> shipment.from_location = storage1
    >>> shipment.to_location = storage2
    >>> shipment.locations.append(Location(pallet.id))
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')  # doctest: +IGNORE_EXCEPTION_DETAIL
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
    True
    >>> shipment2.click('assign_try')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    AssignError: ...

    >>> shipment1.click('done')

Add lead time inside the warehouse::

    >>> LeadTime = Model.get('stock.location.lead_time')
    >>> lead_time = LeadTime()
    >>> lead_time.warehouse_from = storage_loc.warehouse
    >>> lead_time.warehouse_to = storage_loc.warehouse
    >>> lead_time.lead_time = datetime.timedelta(1)
    >>> lead_time.save()

Move pallet from storage1 to storage2 with lead_time::

    >>> Shipment = Model.get('stock.shipment.internal')
    >>> shipment = Shipment()
    >>> shipment.planned_date = tomorrow
    >>> shipment.from_location = storage1
    >>> shipment.to_location = storage2
    >>> shipment.locations.append(Location(pallet.id))
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True

    >>> shipment.click('ship')
    >>> pallet.reload()
    >>> pallet.parent == shipment.transit_location
    True

    >>> shipment.click('done')
    >>> pallet.reload()
    >>> pallet.parent == storage2
    True
