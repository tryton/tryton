.. _Creating a rentals order:

Creating a rentals order
========================

Creating a new rental order is simply a matter of creating a new `Rental
<model-sale.rental>` and adding the lines for the rented `Products
<concept-product>`.
Most of the fields are optional or have sensible default values.

.. tip::

   The rental's reference field is intended to be used to keep track of the
   customers reference for the rental.
   This can be filled in at any time even when the rental is done.

.. _Changing a rentals order:

Changing a rentals order
========================

The `Rental <model-sale.rental>` needs to be in draft state in order to change
the values in most of the fields.

There are also few fields, such as the `Party <party:model-party.party>` and
`Currency <currency:model-currency.currency>`, which become read-only when any
lines are added to the order.

.. _Making a quotation:

Making a quotation
==================

A draft `Rental <model-sale.rental>` can be set to a quotation state waiting to
be confirmed.

.. note::
   The rented products are reserved by creating draft `Stock Moves
   <stock:model-stock.move>`.

.. _Pickup products:

Pickup products
===============

Any products that are rent must be picked up to start its rental period.
To pickup products, you must launch the `Pickup wizard
<wizard-sale.rental.pickup>` and set the picked quantity for each product.

.. _Return products:

Return products
===============

Any picked products must be returned to be invoiced.
To return products, you must launch the `Return wizard
<wizard-sale.rental.return>` and set the returned quantity for each product.

.. _Invoicing a rental:

Invoicing a rental
==================

Once products have been returned, you can generate an invoice by clicking on
:guilabel:`Invoice` button.
When the last product is return, the last invoice is generated automatically.
