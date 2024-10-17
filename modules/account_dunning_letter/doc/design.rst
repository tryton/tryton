******
Design
******

The *Account Dunning Letter Module* extends the following concepts:

.. _model-account.dunning.level:

Dunning Level
=============

The *Dunning Level* is extended with the ability to print a `Letter
<report-account.dunning.letter>` when a dunning is processed that has reached
that level.

.. _model-account.dunning:

Dunning
=======

Reports
-------

.. _report-account.dunning.letter:

Dunning Letter
^^^^^^^^^^^^^^

The *Dunning Letter* report prints one letter per `Party
<party:model-party.party>` containing all of their dunnings and the `pending
payments <account:model-account.move.line>` that have been received but not yet
`reconciled <account:model-account.move.reconciliation>`.
