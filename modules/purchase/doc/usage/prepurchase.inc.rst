.. _Making products purchasable:

Making products purchasable
===========================

Before you can add a `Product <product:concept-product>` to a
`Purchase <model-purchase.purchase>` it must be marked as purchasable.
When you do this you will also be able to set some additional properties such
as the `Unit of Measure <product:model-product.uom>` the product is normally
bought in, and which suppliers are used and their details about the product.

.. _Setting bulk prices:

Setting bulk prices
===================

Suppliers may offer different prices depending on how much of a
`Product <product:concept-product>` is purchased.
In Tryton you can record these prices using the
`Product Supplier <model-purchase.product_supplier>` concept.

.. tip::

   You can set these prices by opening one of the :guilabel:`Suppliers`
   lines shown when viewing a product's details.

.. note::

   To ensure the correct price is chosen when entering in a
   `Purchase <model-purchase.purchase>` you must ensure that the prices are
   ordered correctly.
   The lowest quantity must appear first, going up to the largest quantity
   last.

   This is because Tryton searches through the price lines in
   :guilabel:`Sequence` order, and uses the last price it finds where the
   ordered quantity is equal to, or more than, the price line's quantity.
