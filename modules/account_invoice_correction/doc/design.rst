******
Design
******

The *Account Invoice Correction Module* extends and introduces the following
concepts:

.. _model-account.invoice:

Invoice
=======

When the *Account Invoice Correction Module* is activated, the *Invoice* gets a
:guilabel:`Correct` button to launch the `Correct Invoice
<wizard-account.invoice.correct>` wizard.

.. seealso::

   The `Invoice <account_invoice:model-account.invoice>` concept is introduced
   by the :doc:`Account Invoice Module <account_invoice:index>`.

Wizards
-------

.. _wizard-account.invoice.correct:

Correct Invoice
^^^^^^^^^^^^^^^

The *Correct Invoice* wizard creates a new `Invoice
<account_invoice:model-account.invoice>` based on the selected invoice lines.
Each selected line is added twice, once with the original quantity and a second
time with the inverted quantity, so that the user can change the price of the
first line without changing the actual quantity invoiced.
