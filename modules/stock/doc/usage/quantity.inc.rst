.. _Viewing stock levels:

Viewing stock levels
====================

In Tryton there are a few different ways of seeing
`Product Stock Quantities <concept-product.quantity>`.
You can also easily see what the stock situation was at any time in the past,
and get an idea of what the stock situation will be after any
`Stock Moves <model-stock.move>` that are still being processed have been
completed.

.. note::

   Tryton is designed to allow you to create stock moves even if they
   create negative stock.
   For normal storage locations negative stock levels indicate that more
   stock has been used than was available.
   This suggests that there may be incoming moves to the location that
   have not yet been done, or a mistake has been made that can be resolved
   by `Checking and correcting stock levels`.

   However, although it is possible to create negative stock, you will
   normally use `Shipments <concept-stock.shipment>` to help manage stock
   moves, and a process to `assign them <Assigning shipments>`.
   These respect stock availability and wont allow you to create negative
   stock unless you force them to.

Depending on what you are trying to find out you can get information about
stock levels for either `Products <concept-product>` or
`Locations <model-stock.location>`.

If you are interested in finding out where some particular products are
stored, then once you have selected the products you are interested in, you
can use the menu items in the product's :guilabel:`Open related records` menu.

To view how much stock is in one or more stock locations you first need to
select the locations you are interested in.
Once you have done this you can use the :guilabel:`Products` item from the
:guilabel:`Open related records` menu.
This then shows the total stock that is in all the selected locations.

.. tip::

   From the [:menuselection:`Inventory & Stock --> Locations`] main menu item
   you can quickly get a list of stock in a single location by opening the
   location you are interested in.

.. tip::

   If you have only selected a single location then the stock levels will
   include all the stock in the location's children as well.
   However, if you selected multiple locations then only the stock in the
   selected locations is included, any stock in their child locations is
   *not* included.

.. _Checking and correcting stock levels:

Checking and correcting stock levels
====================================

There are a range of things, such as mispicks, damages and theft, that can
cause the stock levels on Tryton to not match the actual amount of stock
available.

Tryton allows you to check for and correct these discrepancies by performing
an `Inventory <model-stock.inventory>` of a
`Stock Location <model-stock.location>`.
This process is sometimes also called a stocktake, stock count or inventory
check.
How often you need to do this, and to what extent, is very dependent on your
business.
You may do this once a year at the end of your fiscal year, or continuously
by means of a `cycle count`_.

When you create a new inventory you can use the :guilabel:`Complete` button to
complete the creation of the inventory.
This adds a line to the inventory for each product that is expected to be in
the location.

How you go about actually counting the stock will depend on how your stock
location is organised.
If each `Product <concept-product>` is all together and is easy to count,
then you can enter the totals directly into the :guilabel:`Quantity` column.
If there are many different lines in the location, or not all of each product
is together, then you can start the `Count <wizard-stock.inventory.count>`
wizard using the :guilabel:`Count` button to enter the quantities as you go.
In this case, multiple quantities for the same product will be automatically
added together.

For each inventory you can choose how to deal with any lines where the quantity
has been left empty.
You can either keep the stock in the location, or empty it out.

Once the inventory has been finished you use the :guilabel:`Confirm` button
to correct the stock levels on Tryton.

.. _`cycle count`: https://en.wikipedia.org/wiki/Cycle_count
