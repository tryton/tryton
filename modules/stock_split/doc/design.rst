******
Design
******

The *Stock Split Module* introduces or extends the following concepts.

.. _model-stock.move:

Move
====

When the *Stock Split Module* is activated, the `Move <stock:model-stock.move>`
gain a :guilabel:`Split` button to launch the `Split Move
<wizard-stock.move.split>` wizard and another :guilabel:`Unsplit` button to
reverse the operation.

.. seealso::

   The `Move <stock:model-stock.move>` concept is introduced by the :doc:`Stock
   Module <stock:index>`.

Wizards
-------

.. _wizard-stock.move.split:

Split Move
^^^^^^^^^^

The *Split Move* wizard allows to split a move by :guilabel:`Quantity`.
If :guilabel:`Counts` is set, it will split only this number of times.
On occasion there can be a move with the remaining quantity.


.. _concept-stock.shipment:

Shipment
========

When the *Stock Split Module* is activated, the `Supplier Return Shipment
<stock:model-stock.shipment.in.return>`, the `Customer Shipment
<stock:model-stock.shipment.out>` and the `Internal Shipment
<stock:model-stock.shipment.internal>` gain a :guilabel:`Split` button to
launch the `Split Shipment <wizard-stock.shipment.split>` wizard.

Wizards
-------

.. _wizard-stock.shipment.split:

Split Shipment
^^^^^^^^^^^^^^

The *Split Shipment* wizard allows to split a `Shipment
<stock:concept-stock.shipment>` by selecting moves of the shipment shifted to a
new copy of the shipment.
