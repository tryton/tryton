******
Design
******

The *Account Payment SEPA Module* introduces and extends the following concepts:

.. _model-account.payment:

Payment
=======

When the *Account Payment SEPA Module* is activated, the *Payment* gains some
new properties including those used to generate the SEPA messages (``PAIN.001``
and ``PAIN.008``), and the `SEPA Mandate <model-account.payment.sepa.mandate>`.

.. seealso::

   The `Payment <account_payment:model-account.payment>` concept is introduced
   by the :doc:`Account Payment Module <account_payment:index>`.

.. _model-account.payment.sepa.message:

SEPA Message
============

The *SEPA Message* stores the outgoing :abbr:`XML (eXtensible Markup Language)`
message for the `SEPA Payment <model-account.payment>` to be sent and the
incoming XML messages to be parsed, such as ``CAMT.054``, which will update the
corresponding `Payment <model-account.payment>` and mark it as successful or
failed.

.. seealso::

   The SEPA messages can be found by opening the main menu item:

   |Financial --> Payments --> SEPA Messages|__

   .. |Financial --> Payments --> SEPA Messages| replace:: :menuselection:`Financial --> Payments --> SEPA Messages`
   __ https://demo.tryton.org/model/account.payment.sepa.message

.. _model-account.payment.sepa.mandate:

SEPA Mandate
============

The *SEPA Mandate* stores the validation of the mandate that allows the
`Company <company:model-company.company>` to debit money from a `Party
<party:model-party.party>`'s `Bank Account <bank:model-bank.account>`.

.. seealso::

   The SEPA mandates can be found by opening the main menu item:

   |Banking --> SEPA Mandates|__

   .. |Banking --> SEPA Mandates| replace:: :menuselection:`Banking --> SEPA Mandates`
   __ https://demo.tryton.org/model/account.payment.sepa.mandate

Reports
-------

.. _report-account.payment.sepa.mandate:

Mandate
^^^^^^^

The *Mandate* report prints the standard document that the `Party
<party:model-party.party>` must sign to validate the `SEPA Mandate
<model-account.payment.sepa.mandate>`.

.. _model-account.payment.journal:

Payment Journal
===============

When the *Account Payment SEPA Module* is activated, the *Payment Journal*
gains new properties including those for the IBAN `Bank Account
<bank:model-bank.account>`, and the SEPA flavor for the payables and
receivables.

.. seealso::

   The `Payment Journal <account_payment:model-account.payment.journal>`
   concept is introduced by the :doc:`Account Payment Module
   <account_payment:index>`.

.. _model-account.payment.group:

Payment Group
=============

When the *Account Payment SEPA Module* is activated, the *Payment Group* gains
a :guilabel:`Generate SEPA Message` button to save the text files for the `SEPA
messages <model-account.payment.sepa.message>`.

.. seealso::

   The `Payment Group <account_payment:model-account.payment.group>` concept is
   introduced by the :doc:`Account Payment Module <account_payment:index>`.

.. _model-account.configuration:

Account Configuration
=====================

When the *Account Payment SEPA Module* is activated, the *Account
Configuration* gains a property for the `Sequence <trytond:model-ir.sequence>`
to use for the `Mandates <model-account.payment.sepa.mandate>`.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-party.party:

Party
=====

When the *Account Payment SEPA Module* is activated, the *Party* is extended to
list their `SEPA Mandates <model-account.payment.sepa.mandate>`.

Also the direct debits property is extended to set up the `SEPA Mandate
<model-account.payment.sepa.mandate>` to use when `Creating a Direct Debit
<account_payment:wizard-account.move.line.create_direct_debit>`.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.
