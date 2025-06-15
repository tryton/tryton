******
Design
******

The *Account Payment Clearing Module* introduces the following concepts:

.. _model-account.payment:

Payment
=======

When the *Account Payment Clearing Module* is activated, the payment gain some
extra properties.
These include an `Account <account:model-account.account>` to use for clearing
if no `Move Line <account:model-account.move.line>` is set.

.. seealso::

   The `Payment <account_payment:model-account.payment>` concept is introduced
   by the :doc:`Account Payment Module <account_payment:index>`.

Wizards
-------

.. _wizard-account.payment.succeed:

Succeed Payment
^^^^^^^^^^^^^^^

The *Succeed Payment* wizard asks for the date to use for the clearing `Account
Move <account:model-account.move>` before succeeding the payment.

.. note:: The wizard is also used to succeed `Payment Group
   <account_payment:model-account.payment.group>`.

.. _model-account.payment.journal:

Payment Journal
===============

When the *Account Payment Clearing Module* is activated, the payment journal
gain some extra properties that controls the clearing behavior.
These include a clearing account and journal to use to create the `Account Move
<account:model-account.move>` and a clearing delay to post automatically the
created moves.

.. seealso::

   The `Payment Journal <account_payment:model-account.payment.journal>`
   concept is introduced by the :doc:`Account Payment Module
   <account_payment:index>`.
