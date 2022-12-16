.. _Creating a purchase order:

Creating a purchase order
=========================

Creating a new purchase order is simply a matter of creating a new
`Purchase <model-purchase.purchase>` and adding the lines that are
required.
Most of the fields are optional or have sensible default values.

.. tip::

   Product prices are automatically converted to the
   `Currency <currency:model-currency.currency>` used on the purchase.
   To keep the prices fixed when ordering in a foreign currency set the
   currency and prices in the `Product's <product:concept-product>` list of
   `Product Suppliers <model-purchase.product_supplier>`.

.. tip::

   The purchase's reference field is intended to be used to keep track of
   the supplier's reference for the purchase.
   This can be filled in at any time, even when the purchase is done.

.. _Changing a purchase order:

Changing a purchase order
=========================

To be able to change most of the values in the fields on a
`Purchase <model-purchase.purchase>` the purchase must be in a draft state.

There are also a few fields, such as the `Party <party:model-party.party>` and
`Currency <currency:model-currency.currency>`, which become read-only when any
lines are added to the order.
To be able to change these without needing to remove the lines from the
purchase you can use the :guilabel:`Modify Header` button to start the
`Modify Header <wizard-purchase.modify_header>` wizard.

.. _Receiving a shipment:

Receiving a shipment
====================

Goods that are bought as part of a `Purchase <model-purchase.purchase>` are
`received from the supplier <stock:Sending and receiving deliveries>` using a
`Supplier Shipment <stock:model-stock.shipment.in>`.

Suppliers sometimes send a single order on multiple different shipments, or
group several orders together into a single shipment.
As it is not possible to know how a supplier will ship products the
*Purchase Module* does not automatically create any supplier shipments for you.

A purchase does, however, create draft `Stock Moves <stock:model-stock.move>`
for any goods or assets that have been purchased.
Once you receive the information about what's been shipped you create a new
supplier shipment and add these moves to it.

If not all the stock has been sent, then new stock moves are automatically
created for any remaining quantities when the shipment is received, or the
purchase gets processed again.
These can be added to later shipments, split up further, or cancelled.

.. tip::

   The supplier shipments that are related to the purchase can be found using
   the purchase's :guilabel:`Shipments` link.

   The :guilabel:`Shipments` and stock :guilabel:`Moves` related to a purchase
   can also be found using the items in the purchase's
   :guilabel:`Open related records` menu.

.. _Getting invoiced:

Getting invoiced
================

The `Purchase's <model-purchase.purchase>` invoice method determines whether
the purchase will automatically generate draft
`Invoices <account_invoice:model-account.invoice>`.

When you receive the invoice from the supplier you can then find the draft
supplier invoice and check it for any discrepancies, before validating or
posting it.

.. tip::

   The supplier invoices that are related to the purchase can be found using
   the purchase's :guilabel:`Invoices` link, or the :guilabel:`Invoices`
   item found in the sale's :guilabel:`Open related records` menu.

.. _Handling shipment and invoice exceptions:

Handling shipment and invoice exceptions
========================================

Sometimes you may cancel `Stock Moves <stock:model-stock.move>` or
`Invoices <account_invoice:model-account.invoice>` that are related to a
`Purchase <model-purchase.purchase>`.
You may have done this because you no longer need these items, or you may
now need to recreate them.
As Tryton does not know if a cancelled item needs to be recreated, or not,
it shows this as an exception in the purchase's shipment or invoice state.

For purchases that have a shipment or invoice exception you can use the
`Handle Shipment Exception <wizard-purchase.handle.shipment.exception>` or
`Handle Invoice Exception <wizard-purchase.handle.invoice.exception>` wizards
to recreate the items that need recreating, and ignore the rest.

.. tip::

   When using the wizard the moves and invoices to recreate will, by default,
   already be selected.
   This means you will need to deselect any that you do not want to recreate.

.. _Finishing a purchase:

Finishing a purchase
====================

In Tryton once a `Purchase <model-purchase.purchase>` is being processed there
is no button that moves the purchase into a done state.
This will happen automatically once the purchase's
`Shipments <stock:model-stock.shipment.in>` and
`Invoices <account_invoice:model-account.invoice>` are completed.
