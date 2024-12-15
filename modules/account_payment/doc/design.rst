******
Design
******

The *Account Payment Module* introduces the following concepts:

.. _model-account.payment:

Payment
=======

A *Payment* represents an order to pay an amount to a `Party
<party:model-party.party>` or receive an amount from a party.
It may be linked to an `Move Line <model-account.move.line>` to deduce its
*Amount to Pay*.

Once processed, a payment can not be changed except to be succeeded or failed.

When the :doc:`Account Statement Module <account_statement:index>` is
activated, the payment lines linked to a statement line are marked as succeeded
when the statement is validated.

.. seealso::

   The receivable payments can be found by opening the main menu item:

   |Financial --> Payments --> Receivable Payments|__

   .. |Financial --> Payments --> Receivable Payments| replace:: :menuselection:`Financial --> Payments --> Receivable Payments`
   __ https://demo.tryton.org/model/account.payment;domain=[["kind"%2C"%3D"%2C"receivable"]]

   The payable payments can be found by opening the main menu item:

   |Financial --> Payments --> Payable Payments|__

   .. |Financial --> Payments --> Payable Payments| replace:: :menuselection:`Financial --> Payments --> Payable Payments`
   __ https://demo.tryton.org/model/account.payment;domain=[["kind"%2C"%3D"%2C"payable"]]

Wizards
-------

.. _wizard-account.payment.process:

Process Payment
^^^^^^^^^^^^^^^

The *Process Payment* wizard groups the payments of same kind and process them
following the method defined on the journal.

.. _model-account.payment.journal:

Payment Journal
===============

A *Payment Journal* groups `Payments <model-account.payment>`.
It defines the `Currency <currency:model-currency.currency>` and the processing
method.

.. seealso::

   The payment journals can be found by opening the main menu item:

      |Financial --> Configuration --> Payments --> Journals|__

      .. |Financial --> Configuration --> Payments --> Journals| replace:: :menuselection:`Financial --> Configuration --> Payments --> Journals`
      __ https://demo.tryton.org/model/account.payment.journal


.. _model-account.payment.group:

Payment Group
=============

A *Payment Group* contains `Payments <model-account.payment>` processed
together at the same time for methods that need it.
The payment group is used to follow the processing of the payments.

.. seealso::

   The payment groups can be found by opening the main menu item:

      |Financial --> Payments --> Payment Groups|__

      .. |Financial --> Payments --> Payment Groups| replace:: :menuselection:`Financial --> Payments --> Payment Groups`
      __ https://demo.tryton.org/model/account.payment.group


.. _model-account.move.line:

Account Move Line
=================

When the *Account Payment Module* is activated, the account move lines gain
some extra properties.
These include the amount to pay for a receivable or payable line and the
blocked and direct debit checkboxes.

.. seealso::

   The `Account Move Line <account:model-account.move.line>` concept is
   introduced by the :doc:`Account Module <account:index>`.

Wizards
-------

.. _wizard-account.move.line.create_direct_debit:

Create Direct Debit
^^^^^^^^^^^^^^^^^^^

The *Credit Direct Debit* wizard creates receivable payments for due lines for
a date based on the direct debits property of the `Party <model-party.party>`.

.. _wizard-account.move.line.pay:

Pay Line
^^^^^^^^

The *Pay Line* wizard creates payments for each line and using the amount to
pay.


.. _model-party.party:

Party
=====

When the *Account Payment Module* is activated, the parties gain some extra
accounting properties.
These include a checkbox to prevent to pay supplier which does direct debit and
a list of direct debit options to collect payments from customer.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.
