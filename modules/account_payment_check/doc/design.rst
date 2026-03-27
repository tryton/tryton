******
Design
******

The *Account Payment Check Module* introduces and extends the following
concepts:

.. _model-account.payment.journal:

Payment Journal
===============

When the *Account Payment Check Module* is activated, the *Payment Journal*
gains new properties including those for the check `sequence
<trytond:model-ir.sequence.strict>` and `format
<trytond:model-ir.action.report>`.

.. seealso::

   The `Payment Journal <account_payment:model-account.payment.journal>`
   concept is introduced by the :doc:`Account Payment Module
   <account_payment:index>`.

.. _model-account.payment.group:

Payment Group
=============

When the *Account Payment Check Module* is activated, the *Payment Group* gains
a :guilabel:`Print Checks` button.

.. seealso::

   The `Payment Group <account_payment:model-account.payment.group>` concept is
   introduced by the :doc:`Account Payment Module <account_payment:index>`.

Wizards
-------

.. _wizard-account.payment.check.print:

Print Check
^^^^^^^^^^^

The *Print Check* wizard numbers the payments and print them using the format
defined on the `journal <model-account.payment.journal>`.

Reports
-------

.. _report-account.payment.check:

Check
^^^^^

The *Check* report is a document that can be printed out as a check.

.. _model-account.payment:

Payment
=======

When the *Account Payment Check Module* is activated, the *Payment* gains a
:guilabel:`Check Number` property that can be filled in *receivable* payments
and is set automatically for *payable* payments.

.. seealso::

   The `Payment <account_payment:model-account.payment>` concept is introduced
   by the :doc:`Account Payment Module <account_payment:index>`.
