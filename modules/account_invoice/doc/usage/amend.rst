.. _Correcting invoices:

Correcting invoices
===================

`Invoices <model-account.invoice>` can only be changed when they are in a
draft state.

Once an invoice has been posted you will need to
`credit it <Crediting customers and suppliers>`, and reissue it by creating
a new invoice with the correct information on.

.. tip::

   If you need to create a new invoice that is almost the same as an existing
   invoice you can use the :guilabel:`Duplicate` item from the form's menu to
   copy the existing invoice.
   The duplicate invoice will be created in a draft state, so you can change
   anything that was incorrect.

.. _Cancelling invoices:

Cancelling invoices
===================

Most `Invoices <model-account.invoice>` can be cancelled up to the point they
are paid.
Once they are paid you need to credit them instead.
You do this by `creating a credit note <Crediting customers and suppliers>`
for them.

.. note::

   Legislation may not allow you to cancel a posted customer invoice.
   If this is the case, then you should instead create a credit note for it.

   You can allow posted invoices to be credited by changing the setting in your
   `Company <company:model-company.company>`.

Cancelling an invoice removes its effect on your accounts by either removing
its `Account Move <account:model-account.move>`, or negating it with a
cancelling move.

.. _Crediting customers and suppliers:

Crediting customers and suppliers
=================================

In Tryton you credit customers and suppliers by creating *Credit Notes*.
These are just `Invoices <model-account.invoice>` with negative totals.
You can create a credit note manually or create one based on an existing
invoice.

To credit existing invoices you must first select the invoices that need to
be credited.
Next you run the `Credit <wizard-account.invoice.credit>` invoice wizard from
the :guilabel:`Launch action` menu.
