*****
Usage
*****

.. _Assigning productions:

Assigning productions
=====================

The `Productions <model-production>` take stock from storage `Locations
<stock:model-stock.location>` inside the `Warehouse
<stock:concept-stock.location.warehouse>`.
The :guilabel:`Input Materials` must be assigned before they can be done like
:ref:`Shipment <stock:Assigning shipments>`.

.. note::

   The `Scheduled tasks <trytond:model-ir.cron>` :guilabel:`Assign Shipments`
   tries also to assign waiting productions planned for today.
