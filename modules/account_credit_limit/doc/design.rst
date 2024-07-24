******
Design
******

The *Account Credit Limit Module* extends the following concepts:

.. _model-account.configuration:

Account Configuration
=====================

When the *Account Credit Limit Module* is activated, the *Account
Configuration* receives a new property which is used to store the default
credit limit in the `Company <company:model-company.company>`'s currency.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.

.. _model-party.party:

Party
=====

When the *Account Credit Limit Module* is activated, the *Party* gets a new
property that is used to limit how much credit a party can have.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.

.. _model-account.dunning.level:

Dunning Level
=============

When the *Account Credit Limit Module* is activated, the *Dunning Level* can be
flagged to block any additional credit for the `Parties
<party:model-party.party>` who have at least one pending `Dunning
<account_dunning:model-account.dunning>` at that level.

.. seealso::

   The `Dunning Level <account_dunning:model-account.dunning.level>` concept is
   introduced by the :doc:`Account Dunning Module <account_dunning:index>`.
