******
Design
******

The *Stock Shipping Point Module* introduces or extends the following concepts.

.. _model-stock.shipping.point:

Shipping Point
==============

A *Shipping Point* is an entities within a `Warehouse
<stock:concept-stock.location.warehouse>` from which the warehouse ships or
receives goods.

.. seealso::

   The *Shipping Points* can be found by opening the main menu item:

   |Inventory & Stock --> Configuration --> Shipping Points|__

   .. |Inventory & Stock --> Configuration --> Shipping Points| replace:: :menuselection:`Inventory & Stock --> Configuration --> Shipping Points`
   __ https://demo.tryton.org/model/stock.shipping.point

.. _model-stock.shipping.point.selection:

Shipping Point Selection
========================

The *Shipping Point Selection* defines the rules to determine the `Shipping
Point <model-stock.shipping.point>` automatically for outgoing `Shipment
<stock:concept-stock.shipment>` based on criteria such as the delivery `Country
<country:model-country.country>` or the `Product Categories
<product:model-product.category>`.

.. seealso::

   The *Shipping Point Selection* can be found by opening the main menu item:

   |Inventory & Stock --> Configuration --> Shipping Points --> Selection|__

   .. |Inventory & Stock --> Configuration --> Shipping Points --> Selection| replace:: :menuselection:`Inventory & Stock --> Configuration --> Shipping Points --> Selection`
   __ https://demo.tryton.org/model/stock.shipping.point.selection

.. _concept-stock.shipment:

Shipment
========

When the *Stock Shipping Point Module* is activated, the *Shipments* gain new
properties to store the `Shipping Point <model-stock.shipping.point>`.
For outgoing shipments the shipping point is filled automatically by the
`Selection <model-stock.shipping.point.selection>` when set to
:guilabel:`Waiting`.

.. seealso::

   The `Shipment <stock:concept-stock.shipment>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.
