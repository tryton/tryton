******
Design
******

The *Analytic Purchase Module* extends the following concepts:

.. _model-purchase.purchase:

Purchase
========

When the *Analytic Purchase Module* is activated, the *Purchase* line gains a
new property to set one `Analytic Account
<analytic_account:model-analytic_account.account>` per axis.
These analytic accounts are transferred to the generated `Invoice
<analytic_invoice:model-account.invoice>` lines.

.. seealso::

   The `Purchase <purchase:model-purchase.purchase>` concept is introduced by
   the :doc:`Purchase Module <purchase:index>`.
