******
Design
******

The *Account Stock Shipment Cost Module* extends and introduces the following concepts:

.. _concept-product:

Product
=======

When the *Account Stock Shipment Cost Module* is activated, products gain some
extra properties.
This includes a new check-box "Shipment Cost" which is used to indicate that the
service is used as the cost for `Shipments <stock:concept-stock.shipment>`.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-account.shipment.cost:

Shipment Cost
=============

*Shipment Costs* define which posted supplier `Invoice
<account_invoice:model-account.invoice>` lines are linked to which `Shipments
<stock:concept-stock.shipment>`.
When the *Shipment Cost* is posted, the costs from the shipments are added up
and then split up and reallocated to the shipments.

.. seealso::

   Shipment Costs can be found by opening the main menu item:

      |Financial --> Invoices --> Shipment Costs|__

      .. |Financial --> Invoices --> Shipment Costs| replace:: :menuselection:`Financial --> Invoices --> Shipment Costs`
      __ https://demo.tryton.org/model/account.shipment_cost
