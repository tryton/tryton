.. _Cancelling purchases:

Cancelling purchases
====================

You can easily cancel `Purchases <model-purchase.purchase>` that are not yet
confirmed using the :guilabel:`Cancel` button.

Confirmed purchases cannot be cancelled, but you can put them back to a state
where they can be cancelled.
However, as soon as a confirmed purchase starts to be processed it can no
longer be cancelled.
This may happen immediately when it is confirmed, or after a delay if one has
been correctly `Configured <model-purchase.configuration>`.

Once a purchase has started to be processed, to effectively cancel the
purchase, you must cancel its `Stock Moves <stock:model-stock.move>` and
`Invoices <account_invoice:model-account.invoice>`.
Once you have done this you must
`handle the exceptions <Handling shipment and invoice exceptions>`,
ensuring that none of the moves or invoices are selected for
recreation.

.. _Returning purchases:

Returning purchases
===================

There may be times when you need to send a
`Purchase <model-purchase.purchase>`, or part of a purchase, back to the
supplier.
In Tryton this is represented by a purchase that has negative quantities.

One way of creating a supplier return is to select the purchases that you want
to return and then use the `Return Purchase <wizard-purchase.return_purchase>`
wizard.
This creates a draft return purchase for the whole of the selected purchase.

If only part of the purchase is being returned, then the return purchase can
be altered as required.
When it gets processed it will automatically create
`Credit Notes <account_invoice:model-account.invoice>` and
`Supplier Return Shipments <stock:model-stock.shipment.in.return>` where
required.

.. note::

   When processing the return shipment, if the
   `Warehouse <stock:concept-stock.location.warehouse>` has a supplier return
   `Location <stock:model-stock.location>` the returned stock will be taken
   from that location.
   Otherwise the stock will be picked from the warehouse's storage location.
