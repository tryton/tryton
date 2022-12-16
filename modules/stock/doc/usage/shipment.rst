.. _Sending and receiving deliveries:

Sending and receiving deliveries
================================

In Tryton you use `Shipments <concept-stock.shipment>` to send stock to your
customers and receive stock from your suppliers.
There are different kinds of shipments available depending on whether you're
dealing with customers or suppliers and whether you are sending or receiving
stock.

Although each type of shipment helps you manage the delivery of some stock,
and encompasses the same set of ideas, each is tailored for a particular
type of delivery.

From Suppliers
--------------

You use a `Supplier Shipment <model-stock.shipment.in>` when receiving stock
from a supplier.

* The supplier shipment is first received in to the
  `Warehouse's <concept-stock.location.warehouse>`
  input `Location <model-stock.location>`.
* You can then use the
  `Restocking List <report-stock.shipment.in.restocking_list>`
  to help you put the stock away in the right locations in the warehouse.

To Suppliers
------------

If you need to send stock back to a supplier you use a
`Supplier Return Shipment <model-stock.shipment.in.return>`.

To Customers
------------

You use a `Customer Shipment <model-stock.shipment.out>` when sending stock
out to a customer.

* When the customer shipment is waiting to be worked on, normally the first
  thing you need to do is `Assign it <Assigning shipments>`.
* You then pick the stock from the
  `Warehouse <concept-stock.location.warehouse>`.
  A `Picking List <report-stock.shipment.out.picking_list>` helps with this as
  it details how much stock you need, and where it can be found.
* Once you've picked and packed the delivery you can dispatch it to the
  customer from the warehouse's output `Location <model-stock.location>`.
  It is common practice to send a
  `Delivery Note <report-stock.shipment.out.delivery_note>` along with your
  customer's shipment.

From Customers
--------------

Stock that is returned by customers is handled by using a
`Customer Return Shipment <model-stock.shipment.out.return>`.
It works in a similar way to supplier shipments.

* You receive the stock in the warehouse's input location.
* Then you use the `Customer Return Restocking List
  <report-stock.shipment.out.return.restocking_list>` to help you put it away
  in the warehouse.

.. _Moving stock within your company:

Moving stock within your company
================================

If you want to move stock between `Locations <model-stock.location>` within a
`Warehouse <concept-stock.location.warehouse>`, or between warehouses that
belong to the same `Company <company:model-company.company>` you use an
`Internal Shipment <model-stock.shipment.internal>`.

The internal shipment helps you manage the processes of moving stock from one
place to another.

* Once the internal shipment is waiting to be worked on, you need to go ahead
  and `Assign it <Assigning shipments>`.
* You can use the
  `Internal Shipment Report <report-stock.shipment.internal.report>`
  to help you find and pick, or move, the stock.
* If the stock is intended for another warehouse you then send the shipment
  to it.
* Finally once you've put the stock away in the correct locations the internal
  shipment is done.

.. tip::

   You can use the `Stock Location Lead Time <model-stock.location.lead_time>`
   to setup how long it normally takes for shipments between two warehouses.

.. note::

   If an internal shipment is expected to take more than one day to complete
   then when the stock is sent it gets put in a transit location until the
   shipment is done.

.. _Assigning shipments:

Assigning shipments
===================

Any `Shipments <concept-stock.shipment>` types that normally take stock from
either a storage or view `Location <model-stock.location>` must be assigned
before they can be done.
The aim of this process is to find and reserve the stock specifically for the
shipment.

The `Assign Shipment <wizard-stock.shipment.assign>` wizard is used when
assigning shipments.
It tries to `Assign <concept-stock.move.assign>` each of the shipment's
incoming `Stock Moves <model-stock.move>`.
In doing so it updates the stock moves based on what stock it managed to find.

If there is not enough stock available to fully assign the shipment you can
force the remainder to be assigned, although this will result in some stock
locations having negative stock.

.. note::

   When stock moves from a view location are assigned the stock must always be
   taken from one of its sub-locations, as view locations cannot be the
   source or destination of a done move.
   This also means moves from a view location cannot be forced.
