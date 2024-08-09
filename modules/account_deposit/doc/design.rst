******
Design
******

The *Account Deposit Module* extends the following concepts:

.. _model-account.account.type:

Account Type
============

The *Account Type* is extended to define which `Accounts
<account:model-account.account>` can be used for deposits.

.. seealso::

   The `Account Type <account:model-account.account.type>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-account.invoice:

Invoice
=======

A button is added to the *Invoice* to launch the `Recall Deposit
<wizard-account.recall_deposit>` wizard.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account:index>`.

Wizards
-------

.. _wizard-account.recall_deposit:

Recall Deposit
^^^^^^^^^^^^^^

The *Recall Deposit* wizard allows a previous deposit made by the `Party
<party:model-party.party>` of the `Invoice
<account_invoice:model-account.invoice>` to be recalled from a deposit `Account
<account:model-account.account>`.
The wizard adds a line to the *Invoice* with a negative price corresponding to
the maximum amount that is available.

.. _model-party.party:

Party
=====

The *Party* receives a :guilabel:`Deposit` property that calculates the current
amount deposited with the current `Company <company:model-company.company>`.
