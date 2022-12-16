.. _Creating a sales order:

Creating a sales order
======================

Creating a new sales order is simply a matter of creating a new
`Sale <model-sale.sale>` and adding the lines that are required.
Most of the fields are optional or have sensible default values.

.. tip::

   The sale's reference field is intended to be used to keep track of the
   customers reference for the sale.
   This can be filled in at any time even when the sale is done.

.. _Changing a sales order:

Changing a sales order
======================

The `Sale <model-sale.sale>` needs to be in a draft state in order to change
the values in most of the fields.

There are also few fields, such as the `Party <party:model-party.party>` and
`Currency <currency:model-currency.currency>`, which become read-only when any
lines are added to the order.
In order to change these without needing to remove the sales lines you can use
the :guilabel:`Modify Header` button to start the
`Modify Header <wizard-sale.modify_header>` wizard.

.. _Shipping a sale:

Shipping a sale
===============

Any goods that were sold as part of the sale are
`sent to the customer <stock:Sending and receiving deliveries>` using a
`Customer Shipment <stock:model-stock.shipment.out>`.

Depending on the shipment method chosen for the sale, the customer shipment
may be created for you automatically.

.. tip::

   The customer shipments that have been generated from the sale can be found
   using the sale's :guilabel:`Shipments` link.

   The :guilabel:`Shipments` and stock :guilabel:`Moves` related to a sale
   can also be found using the items in the sale's
   :guilabel:`Open related records` menu.

.. _Part shipments:

Part shipments
^^^^^^^^^^^^^^

In some cases you may want to send a sale to a customer in stages.
If you want to do this then you just need to make sure that the shipment's
inventory moves are correct.
Once the shipment is packed, or the sale is processed again, the sale will
automatically create a new shipment that contains any remaining quantities.
This new customer shipment, often referred to as a back-order, can then be
shipped at a later date, split up further, or cancelled.

.. _Invoicing a sale:

Invoicing a sale
================

The `Sale's <model-sale.sale>` invoice method determines whether the sale will
automatically generate `Invoices <account_invoice:model-account.invoice>`.

.. tip::

   The invoices that have been generated from the sale can be found using the
   sale's :guilabel:`Invoices` link or the :guilabel:`Invoices` item found in
   the sale's :guilabel:`Open related records` menu.

.. _Handling shipment and invoice exceptions:

Handling shipment and invoice exceptions
========================================

Sometimes you may have cancelled items from a `Sale's <model-sale.sale>`
`Shipment <stock:model-stock.shipment.out>`, or cancelled a sale's
`Invoice <account_invoice:model-account.invoice>`, and need to recreate
them.
Other times you may have cancelled things because you no longer want to ship,
or invoice, them.
As Tryton does not know if a cancelled item needs to be recreated, or not,
it shows this as an exception in the sale's shipment or invoice state.

For sales that have a shipment or invoice exception you can use the
`Handle Shipment Exception <wizard-sale.handle.shipment.exception>` or
`Handle Invoice Exception <wizard-sale.handle.invoice.exception>` wizards
to recreate the items that need recreating, and ignore the rest.

.. tip::

   When using the wizard the moves and invoices to recreate will, by default,
   already be selected.
   This means you will need to deselect any that you do not want to recreate.

.. _Finishing a sale:

Finishing a sale
================

In Tryton once a `Sale <model-sale.sale>` is being processed there is no
button that moves the sale into a done state.
This will happen automatically once the sale's
`Shipments <stock:model-stock.shipment.out>` and
`Invoices <account_invoice:model-account.invoice>` are completed.
