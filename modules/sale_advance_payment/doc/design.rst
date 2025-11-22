******
Design
******

The *Sale Advance Payment Module* introduces and extends the following
concepts.

.. _model-sale.advance_payment_term:

Sale Advance Payment Term
=========================

The *Sale Advance Payment Term* specifies how the advance payment amount is
calculated for a `Sale <model-sale.sale>`.
This payment allows for the supply and shipping of the sale.

.. seealso::

   Sale advance payment terms are created and managed from the main menu item:

      |Sales --> Configuration --> Advance Payment Terms|__

      .. |Sales --> Configuration --> Advance Payment Terms| replace:: :menuselection:`Sales --> Configuration --> Advance Payment Terms`
      __ https://demo.tryton.org/model/sale.advance_payment_term

.. _model-sale.sale:

Sale
====

When the *Sale Advance Payment Module* is activated, the `Sale
<sale:model-sale.sale>` is extended to allow defining an `Advance Payment Term
<model-sale.advance_payment_term>`.

When the sale is quoted, the advance payment lines are calculated using this
term.

When the sale is processed an `Invoice <account_invoice:model-account.invoice>`
is created for each advance payment line.
The final invoice is generated when these advance payment invoices are paid.
Previously paid amounts are deducted from the final invoice.

.. warning::
   If an advance payment invoice is cancelled and not recreated when processing
   the exception.
   The condition of the cancelled invoice will be concidered as met.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.
