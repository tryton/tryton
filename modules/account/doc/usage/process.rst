.. _Reconciling accounts:

Reconciling accounts
====================

In Tryton account reconciliation is a process that matches up debits and credit
in an `Account <model-account.account>` which balance out to zero.

This allows you to easily see, for example, which payments were for which
transactions, and which things still need to be paid for.
Any `Reconciliation <model-account.move.reconciliation>` that an
`Account Move Line <model-account.move.line>` is part of is shown by the
account move line's :guilabel:`Reconciliation` field.

The `Reconcile Accounts <wizard-account.reconcile>` wizard is used to manually
run this account reconciliation.

.. note::

   Some other processes in Tryton will automatically reconcile account move
   lines when appropriate.
