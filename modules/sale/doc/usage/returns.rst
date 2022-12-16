.. _Cancelling sales:

Cancelling sales
================

You can easily cancel `Sales <model-sale.sale>` that are not yet confirmed
using the :guilabel:`Cancel` button.

Confirmed sales cannot be cancelled, but you can put them back to a state
where they can be cancelled.
However, as soon as a confirmed sale starts to be processed it can no longer
be cancelled.
This may happen immediately when it is confirmed, or after a delay if one has
been correctly `Configured <model-sale.configuration>`.

Once a sale has started to be processed, to effectively cancel the sale,
you must cancel its `Customer Shipments <stock:model-stock.shipment.out>` and
`Invoices <account_invoice:model-account.invoice>`.
Once you have done this you must
`handle the exceptions <Handling shipment and invoice exceptions>` this
generates, ensuring that none of the moves or invoices are selected for
recreation.

.. _Handling customer returns:

Handling customer returns
=========================

Sometimes a customer may decide to return a `Sale <model-sale.sale>`, or part
of a sale, to you.
In Tryton this is represented by a sale that has negative quantities.

One way of creating a customer return is to use the
`Return Sale <wizard-sale.return_sale>` wizard.
This creates a new draft sales return for the whole of the selected sale.

If the customer has only returned part of the sale, then the sales return can
be altered as required.
When it gets processed it will automatically create
`Credit Notes <account_invoice:model-account.invoice>` and
`Customer Return Shipments <stock:model-stock.shipment.out.return>` where
required.
