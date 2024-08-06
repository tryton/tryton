.. _Making products salable:

Making products salable
=======================

Before you can add a `Product <product:concept-product>` to a
`Sale <model-sale.sale>` it must be marked as salable.
When you do this you will also be able to set some additional properties such
as the `Unit of Measure <product:model-product.uom>` the product is normally
sold in and how long it normally takes before the product can be delivered.

.. _Finding sale prices and availability:

Finding sale prices and availability
====================================

Before making a `Sale <model-sale.sale>` it is sometimes useful to know how
much of a `Product <product:concept-product>` is available, and what the sale
price will be.

You can get a list of this information for the salable products by using the
[:menuselection:`Sales --> Salable Products`] main menu item.
The `Sale Context <model-product.sale.context>` allows you to adjust the
various parameters that can effect stock availability and price, such as which
`Warehouse <stock:concept-stock.location.warehouse>` will be supplying the
product, who the customer is and how much they want to buy.

.. tip::

   As with all Tryton data you can export this list to a
   :abbr:`CSV (Comma Separated Value)` file by using the form's
   :guilabel:`Export` menu item.
