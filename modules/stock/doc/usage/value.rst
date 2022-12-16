.. _Finding the value of your stock:

Finding the value of your stock
===============================

In Tryton you can easily find the value of stock that's in one, or more,
`Locations <model-stock.location>` as the stock's cost value is included when
`Viewing stock levels` for the locations you are interested in.

.. _Updating the value of your stock:

Updating the value of your stock
================================

The value of the stock that your `Company <company:model-company.company>`
owns is based on the `Quantity <concept-product.quantity>` of stock and its
cost price.

You can correct the quantity of stock by
`Checking and correcting stock levels`.

You can also change how much the stock is worth by
`Updating a product's cost price`.

.. _Updating a product's cost price:

Updating a product's cost price
===============================

A `Product's <concept-product>` cost price is affected by various factors
including its cost price method and in some cases the value of stock received
or dispatched.

The `Recompute Cost Price <wizard-product.recompute_cost_price>` wizard is
used to update a product's cost price using the product's cost price method.

.. tip::

   Most of the time you will not need to run the wizard that recalculates your
   products' cost prices, because, by default, there is a scheduled task that
   runs once a day and does this for you.

   You can, however, also run the wizard at any time to ensure you are seeing
   the most up to date information.

Once there are some `Stock Moves <model-stock.move>` for a
`Product <concept-product>` you can make a manual adjustment to a product's
cost price using the `Modify Cost Price <wizard-product.modify_cost_price>`
wizard.
This allows you to do things like reduce the cost price, and consequently
stock value, of a product by ``10%`` from a certain date by using
``cost_price * 0.9``.

.. note::

   If you modify a cost price you may also need to run the *Recompute Cost
   Price* wizard to see the changes reflected in the product's cost price.

.. _Viewing cost price changes:

Viewing cost price changes
==========================

You can get a list of any manual cost price changes that have been applied
to a product by using the :guilabel:`Cost Price Revision` relate action from
the product's :guilabel:`Open Related Records` menu.
