******
Design
******

The *Commission Waiting Module* extends the following concepts:

.. _model-commission.agent:

Agent
=====

When the *Commission Waiting Module* is activated, the *Agent* gains a new
property for the `Account <account:model-account.account>` to use to book
their waiting commissions until they are invoiced.

.. seealso::

   The `Agent <commission:model-commission.agent>` concept is introduced by the
   :doc:`Commission Module <commission:index>`.

.. _model-commission:

Commission
==========

When the *Commission Waiting Module* is activated, the *Commission* gains a new
property for the waiting `Account Move <account:model-account.move>` that is
automatically generated if the `Agent <model-commission.agent>` has a waiting
`Account <account:model-account.account>` set.

.. seealso::

   The `Commission <commission:model-commission>` concept is introduced by the
   :doc:`Commission Module <commission:index>`.

.. _model-account.invoice:

Invoice
=======

The *Invoice* concept is extended to also post and clear the waiting `Move
<account:model-account.move>` from the `Commission
<commission:model-commission>` lines when it is posted.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.
