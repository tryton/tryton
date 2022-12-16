.. _model-stock.inventory:

Inventory
=========

The *Inventory* concept is used to help check and correct the amount of
stock stored in a `Location <model-stock.location>`.

Each inventory has a set of lines, one for each `Product <concept-product>`
that is in, or is should be in, the location.
Each line has an expected quantity and an actual quantity.
The former is used to show how much stock is expected to be in the location
and the latter is used to record how much stock was actually found there.

A option on the inventory specifies what to do with lines whose actual
quantity is left empty.

When the *Inventory* is confirmed the stock in the location is updated by
creating a set of `Stock Moves <model-stock.move>`.
These moves correct the stock in the location.
They do this by transferring stock to and from the lost and found location
associated with location being checked.

.. warning::

   Do not use inventories when `Setting initial stock levels`.

.. seealso::

   The inventory checks can be found using the main menu item:

      |Inventory & Stock --> Inventories|__

      .. |Inventory & Stock --> Inventories| replace:: :menuselection:`Inventory & Stock --> Inventories`
      __ https://demo.tryton.org/model/stock.inventory

Wizards
-------

.. _wizard-stock.inventory.count:

Inventory Count
^^^^^^^^^^^^^^^

The *Inventory Count* wizard helps users fill in inventories on a
`Product <concept-product>` by product basis.
It takes a product and a quantity and adds this to the appropriate inventory
line.
