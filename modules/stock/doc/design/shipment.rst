.. _concept-stock.shipment:

Shipment
========

In Tryton the concept of a *Shipment* is used to help organise and manage
groups of related `Stock Moves <model-stock.move>`.
There are different types of shipment which are used for different purposes.
Some of these types of shipment may also be split up into stages.
In each stage stock is moved to or from an intermediate
`Location <model-stock.location>`.
Each stage's moves form a subset of the shipment's total moves.

.. _model-stock.shipment.in:

Supplier Shipment
-----------------

A *Supplier Shipment* has a set of properties that hold details about the
shipment such as who the supplier is, what
`Warehouse <concept-stock.location.warehouse>` it is going to and the date
when the shipment is expected to be delivered.

It is made up from two sets of `Stock Moves <model-stock.move>`:

* Incoming moves, these are used to move stock between a supplier
  `Location <model-stock.location>` and the warehouse's input location, and
* Inventory moves, these then put the stock away in the warehouse's storage
  location, or one of its child locations.

.. note::

   If the warehouse's input location and storage location are the same then
   the inventory moves are not created.

.. seealso::

   The supplier shipments can be found by opening the main menu item:

      |Inventory & Stock --> Supplier Shipments|__

      .. |Inventory & Stock --> Supplier Shipments| replace:: :menuselection:`Inventory & Stock --> Supplier Shipments`
      __ https://demo.tryton.org/model/stock.shipment.in

Reports
^^^^^^^

.. _report-stock.shipment.in.restocking_list:

Restocking List
"""""""""""""""

The *Restocking List* report lists the items on an incoming shipment and the
destination locations for the stock based on the inventory moves.

.. _model-stock.shipment.in.return:

Supplier Return Shipment
------------------------

A *Supplier Return Shipment* has a set of properties that contain information
about the shipment such as who the supplier was, what
`Address <party:model-party.address>` the shipment is going to, and the date
the shipment is sent.

It is made up from a single set of `Stock Moves <model-stock.move>` that return
the stock directly back to a supplier `Location <model-stock.location>`.

.. seealso::

   The supplier shipments can be found by opening the main menu item:

      |Inventory & Stock --> Supplier Shipments --> Supplier Return Shipments|__

      .. |Inventory & Stock --> Supplier Shipments --> Supplier Return Shipments| replace:: :menuselection:`Inventory & Stock --> Supplier Shipments --> Supplier Return Shipments`
      __ https://demo.tryton.org/model/stock.shipment.in.return

.. _model-stock.shipment.out:

Customer Shipment
-----------------

A *Customer Shipment* has a set of properties that contain information about
the shipment such as which `Warehouse <concept-stock.location.warehouse>` it
is being sent from, what `Address <party:model-party.address>` it is being
delivered to, and the date it is being sent.

A customer shipment is made up from two sets of
`Stock Moves <model-stock.move>`:

* Inventory moves, these moves are used to pick the stock from the warehouse's
  storage `Location <model-stock.location>` and put it in the output location,
  and
* Outgoing moves, these then take the picked stock and send it to a
  customer location.
  The outgoing moves are created first and define what stock needs to be sent
  to the customer.

.. note::

   If the warehouse's picking location (or storage location if no picking
   location is defined) is the same as its output location then only
   outgoing moves are created and these moves do not get
   `Assigned <concept-stock.move.assign>`.

.. seealso::

   The customer shipments can be found by opening the main menu item:

      |Inventory & Stock --> Customer Shipments|__

      .. |Inventory & Stock --> Customer Shipments| replace:: :menuselection:`Inventory & Stock --> Customer Shipments`
      __ https://demo.tryton.org/model/stock.shipment.out

Reports
^^^^^^^

.. _report-stock.shipment.out.picking_list:

Picking List
""""""""""""

The *Picking List* report lists the stock that is needed for a shipment.
For each item on the shipment it details the location the stock should be
taken from, and how much should be taken.

.. _report-stock.shipment.out.delivery_note:

Delivery Note
"""""""""""""

The *Delivery Note* report contains information about where the shipment is
being sent, and when the delivery is happening.
It also lists all the items on the shipment.

.. _model-stock.shipment.out.return:

Customer Return Shipment
------------------------

A *Customer Return Shipment* has properties that contain information about
which customer the stock is being returned from, which
`Warehouse <concept-stock.location.warehouse>` it is sent to and the date the
return is happening.

It is made up from two sets of `Stock Moves <model-stock.move>`:

* Incoming moves, these are used to move stock between a customer
  `Location <model-stock.location>` and the warehouse's input location, and
* Inventory moves, these then put the stock away in the warehouse's storage
  location, or one of its child locations.

.. note::

    If the warehouse's input location and storage location are the same then
    the inventory moves are not created.

.. seealso::

   The customer shipments can be found by opening the main menu item:

      |Inventory & Stock --> Customer Shipments --> Customer Return Shipments|__

      .. |Inventory & Stock --> Customer Shipments --> Customer Return Shipments| replace:: :menuselection:`Inventory & Stock --> Customer Shipments --> Customer Return Shipments`
      __ https://demo.tryton.org/model/stock.shipment.out.return

Reports
^^^^^^^

.. _report-stock.shipment.out.return.restocking_list:

Customer Return Restocking List
"""""""""""""""""""""""""""""""

The *Customer Return Restocking List* report lists the items that were
returned by a customer.
For each item a destination location for the stock is also included based on
the inventory moves.

.. _model-stock.shipment.internal:

Internal Shipment
-----------------

An internal shipment allows a group of `Stock Moves <model-stock.move>`,
between locations within the same `Company <company:model-company.company>`,
to be managed as a single entity.

For internal shipments that are planned to start and end on different dates it
is made up from two sets of moves.
The first set are outgoing moves that put the stock in a transit
`Location <model-stock.location>` and the second set are incoming moves that
take the stock from the transit location and place it in the destination
location.

.. seealso::

   Internal shipments are available from the main menu item:

      |Inventory & Stock --> Internal Shipments|__

      .. |Inventory & Stock --> Internal Shipments| replace:: :menuselection:`Inventory & Stock --> Internal Shipments`
      __ https://demo.tryton.org/model/stock.shipment.internal

Reports
^^^^^^^

.. _report-stock.shipment.internal.report:

Internal Shipment Report
""""""""""""""""""""""""

The *Internal Shipment Report* provides a list of the items on the internal
shipment along with their quantities.
For shipments between `Warehouses <concept-stock.location.warehouse>` it also
contains the `Address <party:model-party.address>` of the warehouse the stock
is being sent to.

Wizards
-------

.. _wizard-stock.shipment.assign:

Assign Shipment
^^^^^^^^^^^^^^^

The *Assign Shipment* wizard is used to assign a shipment.
Assigning a shipment tries to `Assign <concept-stock.move.assign>` the
`Stock Moves <model-stock.move>` that take the stock for the shipment.
If not all the stock moves can be assigned then it provides the user with a
set of options of what to do next.
