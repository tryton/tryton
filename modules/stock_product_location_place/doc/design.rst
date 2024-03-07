******
Design
******

The *Stock Product Location Place* introduces or extends to following concepts.

.. _model-stock.product.location.place:

Product Location Place
======================

The *Product Location Place* stores the place where the `Product
<product:concept-product>` is stored inside the `Location
<stock:model-stock.location>`.

.. _model-stock.move:

Move
====

The *Move* is extended to display the place of the `Product
<product:model-product.product>` for each `Stock Locations
<stock:model-stock.location>`.

.. seealso::

   The `Move <stock:model-stock.move>` concept is introduced by the :doc:`Stock
   Module <stock:index>`.

.. _concept-product:

Product
=======

The *Product* concept is extended to manage its `Product Location Places
<model-stock.product.location.place>`.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.
