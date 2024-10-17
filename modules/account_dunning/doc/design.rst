******
Design
******

The *Account Dunning Module* introduces the following concepts:

.. _model-account.dunning.procedure:

Dunning Procedure
=================

A *Dunning Procedure* defines the steps to be followed for overdue `receivables
<account:model-account.move.line>`.
The steps are defined by an ordered list of `Levels
<model-account.dunning.level>`.

.. seealso::

   A list of the Dunning Procedures is available from the main menu item:

      |Financial --> Configuration --> Dunnings --> Procedures|__

      .. |Financial --> Configuration --> Dunnings --> Procedures| replace:: :menuselection:`Financial --> Configuration --> Dunnings --> Procedures`
      __ https://demo.tryton.org/model/account.dunning.procedure

.. _model-account.dunning.level:

Dunning Level
=============

Each level contains the criteria, such as the overdue duration, that a `Dunning
<model-account.dunning>` must meet to reach it.

.. _model-account.dunning:

Dunning
=======

A *Dunning* follows the dunning process for an overdue receivable `Move Line
<account:model-account.move.line>` through the levels of the linked `Procedure
<model-account.dunning.procedure>`.

It is possible to block a dunning from going onto a later level.

Once the move line is reconciled, the dunning is automatically removed.

.. seealso::

   The Dunnings can be found by opening the main menu item:

      |Financial --> Dunnings --> Dunnings|__

      .. |Financial --> Dunnings --> Dunnings| replace:: :menuselection:`Financial --> Dunnings --> Dunnings`
      __ https://demo.tryton.org/model/account.dunning

Wizards
-------

.. _wizard-account.dunning.create:

Create Dunnings
^^^^^^^^^^^^^^^

The *Create Dunnings* wizard creates the `Dunnings <model-account.dunning>` for
each receivable `Line <account:model-account.move.line>` that is more overdue
then the entered date and increases the level of the waiting dunnings if they
meet the criteria.

.. seealso::

   The Create Dunnings wizard can be launch from the main menu item:

      |Financial --> Dunnings --> Create Dunnings|__

      .. |Financial --> Dunnings --> Create Dunnings| replace:: :menuselection:`Financial --> Dunnings --> Create Dunnings`
      __ https://demo.tryton.org/wizard/account.dunning.create

.. _wizard-account.dunning.process:

Process Dunning
^^^^^^^^^^^^^^^

The *Process Dunning* wizard performs the actions required for the level of the
selected draft `Dunnings <model-account.dunning>` and puts them in a waiting
state.

.. note::

   As the action for a certain level can be grouped by `Party
   <party:model-party.party>`, the wizard is launched from the list of
   *Dunnings*.

.. _wizard-account.dunning.reschedule:

Reschedule Dunning
^^^^^^^^^^^^^^^^^^

The *Reschedule Dunning* wizard launches the `Reschedule Lines
<account:wizard-account.move.line.reschedule>` wizard for the `Dunning
<model-account.dunning>`'s `Line <account:model-account.move.line>`.

.. _model-party.party:

Party
=====

When the *Account Dunning Module* is activated, it is possible to define the
`Dunning Procedure <model-account.dunning.procedure>` to follow for the party's
overdue `Lines <account:model-account.move.line>`.

.. seealso::

   The `Party <party:model-party.party>` concept is introduced by the
   :doc:`Party Module <party:index>`.

.. _model-account.configuration:

Account Configuration
=====================

When the *Account Dunning Module* is activated, the *Account Configuration*
gets a new property that is used to set the default `Dunning Procedure
<model-account.dunning.procedure>` for new `Parties <party:model-party.party>`.

.. seealso::

   The `Account Configuration <account:model-account.configuration>` concept is
   introduced by the :doc:`Account Module <account:index>`.
