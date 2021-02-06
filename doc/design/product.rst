.. _concept-product:

Product
=======

When the *Stock Module* is activated, products gain some extra properties.
These include a product's stock and forecast quantities, which show its
current and predicted future stock situation, and the cost value of its
stock.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.

.. _concept-product.quantity:

Product Quantity
----------------

The amount, and the value, of a product in a
`Stock Location <model-stock.location>` is calculated by adding up all the
`Stock Moves <model-stock.move>` in to that location and subtracting those
out of the same location.

Some values from the
:attr:`Transaction context <trytond:trytond.transaction.Transaction.context>`
are used to help determine which stock moves get included in this calculation
and which get left out.
These values include things like which locations to include in the
calculation, and what dates should be included.

Normally, when calculating stock quantities for a date in the past, only moves
that are done are included in the calculation, and only if their effective
date is early enough.
This reflects the real situation based on completed stock moves.
For dates in the future, draft and `Assigned <concept-stock.move.assign>`
moves are also included, but only if their planned date is between today's
date and the future date, inclusive.

.. note::

   The stock quantity of consumable products is calculated in exactly
   the same way as any other product, even though consumable products
   can always be assigned regardless of how much stock there is.

Wizards
-------

.. _wizard-product.recompute_cost_price:

Recompute Cost Price
^^^^^^^^^^^^^^^^^^^^

The *Recompute Cost Price* wizard updates products' cost prices using their
cost price method.

.. _wizard-product.modify_cost_price:

Modify Cost Price
^^^^^^^^^^^^^^^^^

The *Modify Cost Price* wizard is only way in which a product's cost price
can be changed once it has stock moves.
The wizard takes a date and a fixed price or formula for the new cost price.
These changes are stored in the
`Cost Price Revision <model-product.cost_price.revision>` concept and are
applied at the beginning of the date that was selected when the cost price
of the product gets re-calculated.

.. _model-stock.product_quantities_warehouse:

Product Quantities by Warehouse
===============================

The idea of the *Product Quantities by Warehouse* concept is to provide
information about how the stock levels of one or more products have varied
over time in a particular `Warehouse <concept-stock.location.warehouse>`.

.. _model-stock.product_quantities_warehouse.move:

Product Quantities by Warehouse Move
====================================

The *Product Quantities by Warehouse Move* concept provides information about
how `Stock Moves <model-stock.move>` have affected the stock levels in a
`Warehouse <concept-stock.location.warehouse>` over time.

.. _model-product.cost_price.revision:

Cost Price Revision
===================

The *Cost Price Revision* records changes to a product's cost price.
These revisions are automatically created when the product's cost price is
changed using the `Modify Cost Price <wizard-product.modify_cost_price>`
wizard.
