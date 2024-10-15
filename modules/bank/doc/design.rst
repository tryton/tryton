******
Design
******

The *Bank Module* introduces and extends the following concepts:

.. _model-bank:

Bank
====

The *Bank* associates a `Party <party:model-party.party>` with a BIC_.
A *Bank* can be created transparently when creating a `Bank Account
<model-bank.account>` with an IBAN_.

.. seealso::

   The *Banks* can be found by opening the main menu item:

   |Banking --> Banks|__

   .. |Banking --> Banks| replace:: :menuselection:`Banking --> Banks`
   __ https://demo.tryton.org/model/bank

.. _model-bank.account:

Bank Account
============

The *Bank Account* represents an account at a `Bank <model-bank>`.
A *Bank Account* can have different types of numbers including an IBAN_ and
multiple `Owners <party:model-party.party>`.

.. seealso::

   The *Bank Accounts* can be found by opening the main menu item:

   |Banking --> Accounts|__

   .. |Banking --> Accounts| replace:: :menuselection:`Banking --> Accounts`
   __ https://demo.tryton.org/model/bank.account

.. _model-party.party:

Party
=====

When the *Bank Module* is activated, the *Party* gains a new property that
lists the :guilabel:`Bank Accounts` owned by the party.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.

.. _BIC: http://en.wikipedia.org/wiki/Bank_Identifier_Code
.. _IBAN: https://en.wikipedia.org/wiki/International_Bank_Account_Number
