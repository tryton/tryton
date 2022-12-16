*****
Usage
*****

.. _Defer line from invoice

Defer line from invoice
=======================

You can fill a period on the `Invoice <account_invoice:model-account.invoice>`
Line of service.
In this case when the invoice is posted, a draft `Invoice Deferred
<model-account.invoice.deferred>` is created for each line filled.
