Stock Module
############

The stock module defines fundamentals for all stock management
situations: Locations where product are stored, moves between these
locations, shipments for product arrivals and departures and inventory
to control and update stock levels.

Location
********

Locations are generic places where products are physically or
virtually stored. There are seven types of locations:

* Storage

  Storage locations define real places where products are stored.


* Warehouse

  Warehouses are meta-locations which define input, storage, picking and output
  locations. These locations are all of type Storage. Input and Output are
  locations where incoming an outgoing product are temporally stored awaiting
  transportation. The storage location is often the biggest location where
  products are stored for middle or long periods of time. The picking location
  is optionally where the products are picked by the customer shipment
  otherwise the storage location is used.

* Customer

  Customer locations are virtual locations accumulating products that
  have been sent to customers.

* Supplier

  Supplier locations are virtual locations accumulating products that have
  been received from suppliers.

* Lost And Found

  Lost And Found locations collects inventory gaps. See
  :ref:inventory for details.

* Drop

  Drop locations are virtual locations used as intermediary locations in the
  process of drop shipping.

Locations are organised in tree structures, allowing to define
fine grained structures.


Move
****

A move is a movement of a product in a given quantity between two
locations. It may eventually defines a unit price and a currency for
the products that are moved from or to another company, allowing to
compute stock value at any time (and to update the cost prices if the
choosen cost price method is *Average*). A move also defines a planned
date (when one plan to do the move) and an effective date (when the
move is actually made). Products that are used in stock move must of
of type *Goods* or *Assets*. Stock levels are ignored for
consumable, this means that they can be always assigned. *Service*
products are ignored by the stock module.

A move can be in one of this states:

* Draft

  The initial state, used when the move is created and to define
  future stock movement that are planned, but still subject to
  modifications.

* Assigned

  An assigned move allow to reserve some products. Thus preventing
  other user to assign them.

* Done

  The move is in state Done when the real movement is made.

* Cancel

  A cancelled move will be ignored by the system. Only Draft or
  Assigned move can be cancelled. To revert a move in state Done, an
  opposite move must be created.

* Staging

  A phantom state used to create in advance move that should not be taken for
  stock computation.


Product Quantities
++++++++++++++++++

Product quantities on each location are the sum of all moves coming
from or going to this location.  For quantities that are computed for
a date in the past, only confirmed moves (i.e. in state Done) with an
effective date inferior to the considered date are taken into account,
reflecting the real situation. For future quantities, Draft and
Assigned move with a planned date greater than today and smaller than
the given date are also summed.


Shipment
********

A Shipment define a group of moves happening at the same date and
around the same location.


Supplier Shipment
+++++++++++++++++

A supplier shipment is used when products are received from a
supplier. It is mainly composed of a party (the supplier), a location
(the warehouse in which the products are coming) and two list of moves:

* Incoming moves

  The moves between the supplier location and the input location
  (as defined on the warehouse).

* Inventory moves

  The inventory moves are between the input location and the storage
  location (or one of his child locations).


The supplier shipment can be in one of this states:

* Draft

  Incoming moves and inventory moves (if they exist) are in draft.

* Received

  Incoming move are set in state Done, inventory moves are created if
  necessary.

* Done

  Inventory and incoming moves are in state Done.

* Cancel

  All moves are cancelled.


Customer Shipment
+++++++++++++++++

A customer shipment is used for sending products to customer. It is
mainly composed of a party (the customer), a location (the warehouse
out of which the product are going) and two list of moves:

* Inventory moves

  The moves between the picking or storage location and the output location of
  the warehouse

* Outgoing moves

  The moves between the output location of the warehouse and a
  customer location.


The customer shipment can be in one of this states:

* Draft

  Outgoing moves and inventory moves (if they exist) are in draft.

* Waiting

  When a customer shipment is set to waiting, the inventory moves are
  created (or completed) to balance the outgoing moves. The waiting
  state also means that the shipment should be processed.

* Assigned

  The assigned state is when products have been assigned (or reserved)
  from the storage locations.

* Packed

  The packed state is when the inventory moves have been made, i.e
  when the products have been physically moved to the outgoing
  locations.

* Done

  The shipment is Done when the outgoing moves have been made,
  e.g. when a truck left the warehouse.

* Cancel

  A shipment which is not yet completed (not in state Done) can be
  cancelled at any time. This also cancel all the moves.


Internal Shipment
+++++++++++++++++

An internal shipment is used for sending products across locations
inside the company. It is mainly composed of two locations and a list
of moves. It can be in one of these states:


* Draft

  The moves (if they exist) are in draft.

* Waiting

  The waiting state means that the shipment should be processed.

* Assigned

  The assigned state is when products have been assigned.

* Done

  The shipment is Done when the moves have been made.

* Cancel

  A shipment which is not yet completed (not in state Done) can be
  cancelled at any time. This also cancel all the moves.



Inventory
*********

Inventories allow to control and update stock levels. They are mainly
composed of two locations (a Storage location and a Lost And Found
location), and a list of inventory lines. A button allow to
auto-complete inventory lines with respect to the expected quantities
for each product in the location. Inventory lines consist of: a
product and it's default unit of measure, an expected quantity and the
real quantity (the real products on the shelves).

When the inventory is confirmed, moves are created to balance expected
quantities and real ones.
