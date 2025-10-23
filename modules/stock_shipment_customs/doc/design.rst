******
Design
******

The *Stock Shipment Customs Module* introduces or extends the following
concepts.


.. _model-stock.move:

Move
====

When the *Stock Shipment Customs Module* is activated, the `Move
<stock:model-stock.move>` gains a :guilabel:`Customs Unit Price` to store a
different unit price for customs purposes.

.. seealso::

   The `Move <stock:model-stock.move>` concept is introduced by the :doc:`Stock
   Module <stock:index>`.

.. _concept-stock.shipment:

Shipment
========

When the *Stock Shipment Customs Module* is activated, the `Customer Shipment
<stock:model-stock.shipment.out>` and the `Supplier Return Shipment
<stock:model-stock.shipment.in.return>` gain some extra properties for customs.
These include a :guilabel:`Customs Agent` and a :guilabel:`Tax Identifier` for
international shipping.

Reports
^^^^^^^

.. _report-customs.commercial_invoice:

Commercial Invoice
""""""""""""""""""

The *Commercial Invoice* report serves as a customs declaration.
It includes all the information that is needed when exporting goods across
international borders.
