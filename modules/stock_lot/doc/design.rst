******
Design
******

The *Stock Lot Module* introduces or extends the following concepts:

.. _model-stock.lot:

Lot
===

A *Lot* represents a set of a single `Product <product:model-product.product>`,
often delivered or manufactured at the same time.
Among other properties, a *Lot* has a number to identify it.
The *Lot* is associated with a batch of stock by tagging the `Stock Moves
<stock:model-stock.move>` of the products with that *Lot*.

.. seealso::

   The stock lots can be found by opening the main menu item:

      |Inventory & Stock --> Lots|__

      .. |Inventory & Stock --> Lots| replace:: :menuselection:`Inventory & Stock --> Lots`
      __ https://demo.tryton.org/model/stock.lot

.. _concept-lot.quantity:

Lot Quantity
------------

The amount of a *Lot* in a `Stock Location <stock:model-stock.location>` is
calculated in the same way as the `Product Quantity
<stock:concept-product.quantity>` with a filter on the `Stock Moves
<model-stock.move>`.

Wizards
-------

.. _wizard-stock.move.add.lots:

Add Lots
^^^^^^^^

The *Add Lots* wizard allows the user to easily add multiple *Lots* to a `Stock
Move <stock:model-stock.move>` by defining a lot number and quantity.
The *Stock Move* is then split and assigned to the *Lots*.

.. _model-stock.lot.trace:

Lot Trace
=========

The *Lot Trace* shows the usage of a *Stock Lot* over time by displaying the
upward and downward traces as a tree structure.
This is used to provide full `Traceability
<https://en.wikipedia.org/wiki/Traceability>`_ for each stock lot.

.. _model-stock.inventory:

Inventory
=========

The `Inventory <stock:model-stock.inventory>` is extended to allow the `Stock
Lot <model-stock.lot>` to be specified along with the `Product
<product:concept-product>` for each line.

.. _model-product.product:

Product
=======

When the *Stock Lot Module* is activated, products get some additional
properties.
These include a list of `Location <stock:model-stock.location>` types where a
lot is required when the product is moved from or to them.
A sequence can be defined to automatically generate lot numbers for the
product.
A default value for all products can be set for all products in the `Product
Configuration <product:model-product.configuration>`.

.. seealso::

   The `Product <product:concept-product>` concept is introduced by the
   :doc:`Product Module <product:index>`.
