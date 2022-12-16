*****
Setup
*****

.. _Setting up stock locations:

Setting up stock locations
==========================

The *Stock Module* provides a set of default
`Stock Locations <model-stock.location>`, however it is likely that you will
want to customise them to suit your company.

.. tip::

   If you only have a small `Warehouse <concept-stock.location.warehouse>`
   you can use the same location for its storage, input and output locations.
   This reduces the stock moves required to send and receive shipments.

.. tip::

   If you have a large number of locations in your warehouse you can
   use the option to limit locations to only a single level of children.
   This will improve the performance of Tryton when it is calculating
   stock quantities.

.. tip::

   If you are altering your stock locations, and you have already used a
   stock location then it cannot be deleted.
   However, you can deactivate it which will hide it during normal use.

.. _Setting initial stock levels:

Setting initial stock levels
============================

When you start using Tryton you may already have some stock that you want to
bring into the system.

In order to ensure the value of your stock is correctly calculated, and to
show that this stock has (at some point in the past) come from a supplier,
you must enter this initial stock in the correct way.

The right way of doing this is to create a set of individual
`Stock Moves <model-stock.move>`.
These moves can be created in the view that is opened from the
|Inventory & Stock --> Moves|__ main menu item.
Each of the stock moves should move some stock of a `Product <concept-product>`
from a supplier `Location <model-stock.location>` to the appropriate storage
location.
These stock moves must have their unit prices set to their product's cost
price.

.. |Inventory & Stock --> Moves| replace:: :menuselection:`Inventory & Stock --> Moves`
__ https://demo.tryton.org/model/stock.move

.. note::

   As these moves are for your initial stock they have no origin, and
   when you try and do these moves Tryton will warn you about this.
   Because this is for your initial stock this is not a problem, and you
   can safely go ahead and finish doing the moves.

.. tip::

   If you create all the stock moves to start with, you can then select them
   all in the list view, and use the :guilabel:`Do` item from the
   :guilabel:`Launch Action` menu to do them all in one go.
