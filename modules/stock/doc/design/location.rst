.. _model-stock.location:

Location
========

A location represents the place where stock is stored.
This may be a physical location, such as a shelf, or a virtual location such
as the location used for products that have gone missing.

Locations are organised in to a structure with each location having a parent
location and zero or more sub-locations.
It is possible to restrict a location to only one level of children.
This enables the use of an optimisation that improves the performance of the
the stock quantity calculation.

A location also has a set of properties that allow the :ref:`current and
forecasted amounts of stock <concept-product.quantity>` in the location to be
obtained along with the stock's value.

.. _concept-stock.location.warehouse:

Warehouse
---------

Warehouses are special locations that represent a physical warehouse and as
such can have an `Address <party:model-party.address>`.
They are also normally split up into a set of locations each with a particular
purpose, such as for the input, output or storage of stock.

.. seealso::

   Stock locations can be added, removed and changed from the main menu item:

      |Inventory & Stock --> Configuration --> Locations|__

      .. |Inventory & Stock --> Configuration --> Locations| replace:: :menuselection:`Inventory & Stock --> Configuration --> Locations`
      __ https://demo.tryton.org/model/stock.location

   The stock locations structure, and access to the stock levels in
   a location can be found from the main menu item:

      :menuselection:`Inventory & Stock --> Locations`

.. _model-stock.location.lead_time:

Location Lead Time
==================

A *Location Lead Time* is the amount of time that it normally takes to
transfer stock between two `Warehouses <concept-stock.location.warehouse>`.

.. seealso::

   Location lead times can be updated from the main menu item:

      |Inventory & Stock --> Configuration --> Locations --> Location Lead Times|__

      .. |Inventory & Stock --> Configuration --> Locations --> Location Lead Times| replace:: :menuselection:`Inventory & Stock --> Configuration --> Locations --> Location Lead Times`
      __ https://demo.tryton.org/model/stock.location.lead_time
