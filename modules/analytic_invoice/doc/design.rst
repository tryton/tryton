******
Design
******

The *Analytic Invoice Module* extends the following concepts:

.. _model-account.invoice:

Invoice
=======

When the *Analytic Invoice Module* is activated, the *Invoice* line gains a new
property to set one `Analytic Account
<analytic_account:model-analytic_account.account>` per axis.
These analytic accounts are set on the generated `Account Move lines
<analytic_account:model-account.move.line>`.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.

.. _model-account.asset:

Asset
=====

When the *Analytic Invoice Module* is activated, the *Asset* gains a new
property to set one `Analytic Account
<analytic_account:model-analytic_account.account>` per axis.
These analytic accounts are set on the generated `Account Move Lines
<analytic_account:model-account.move.line>` with the expense, revenue and
counterpart accounts.

.. seealso::

   The `Asset <account_asset:model-account.asset>` concept is introduced by the
   :doc:`Account Asset Module <account_asset:index>`.
