******
Design
******

The *Stock Ethanol Module* introduces or extends the following concepts.

.. _model-stock.move:

Move
====

When the *Stock Ethanol Module* is activated, the stock *Move* gains new
properties that calculate the volume of alcohol moved.

.. seealso::

   The `Move <stock:model-stock.move>` concept is introduced by the :doc:`Stock
   Module <stock:index>`.

.. _concept-product:

Product
=======

When the *Stock Ethanol Module* is activated, the *Product* concept gains new
properties that define whether the product contains alcohol and its volume per
`unit <product:model-product.uom>`.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _model-product.price_list:

Price List
==========

When the *Stock Ethanol Module* is activated, a new parameter based on the
volume of ethanol is added to the *Price List* formula.

.. seealso::

   The Price List concept is introduced by the :doc:`Product Price List Module
   <product_price_list:index>`.
