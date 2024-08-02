******
Design
******

The *Analytic Sale Module* extends the following concepts:

.. _model-sale.sale:

Sale
====

When the *Analytic Sale Module* is activated, the *Sale* line gains a
new property to set one `Analytic Account
<analytic_account:model-analytic_account.account>` per axis.
These analytic accounts are transferred to the generated `Invoice
<analytic_invoice:model-account.invoice>` lines.

.. seealso::

   The `Sale <sale:model-sale.sale>` concept is introduced by the :doc:`Sale
   Module <sale:index>`.
