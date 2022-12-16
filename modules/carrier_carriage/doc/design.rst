******
Design
******

The *Carrier Carriage Module* introduces or extends the following concepts.

.. _model-stock.shipment.carriage:

Shipment Carriage
=================

The *Shipment Carriage* stores the information about carriers used before or
after the main carrier for a `Shipment <stock:concept-stock.shipment>`.

.. _concept-stock.shipment:

Shipment
========

The `Supplier <stock:model-stock.shipment.in>`, `Customer
<stock:model-stock.shipment.out>` and `Customer Return
<stock:model-stock.shipment.out.return>` Shipment are extended to store the
`carriers <model-stock.shipment.carriage>` used before and after the main
carrier.

.. seealso::

   The `Shipment <stock:concept-stock.shipment>` concept is introduced by the
   :doc:`Stock Module <stock:index>`.

.. _model-sale.carriage:

Sale Carriage
=============

The *Sale Carriage* stores the information of the available carriers to use
before or after the main carrier for a `Sale <sale:model-sale.sale>`.

.. _model-sale.sale:

Sale
====

When the :doc:`Sale Shipment Cost Module <sale_shipment_cost:index>` is
activated, the *Sale* concept is extended to store the `carriers
<model-sale.carriage>` used before and after the main carrier.
The carriages are copied to the `Customer Shipment
<stock:model-stock.shipment.out>`.
At the quotation, a shipment cost *Sale Line* is added per carriages with a
*Cost Method*.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.

.. _model-incoterm.incoterm:

Incoterm
========

The *Incoterm* concept is extended to add criteria for before and after
carrier.

.. seealso::

   The `Incoterm <incoterm:model-incoterm.incoterm>` concept is introduced by
   the :doc:`Incoterm Module <incoterm:index>`.
