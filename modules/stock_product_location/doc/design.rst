******
Design
******

The *Stock Product Location Module* extends the following concepts.

.. _concept-product:

Product
=======

When the *Stock Product Location Module* is activated, products gain a list of
locations.
These define the preferred storage `Locations <stock:model-stock.location>` to
use, by default, when things like `Shipments <stock:concept-stock.shipment>` or
Productions need to move products.
For consumable products, these also define the fallback locations which are
used when picking items that are out of stock.
