******
Design
******

The *Account Dunning Fee Module* introduces or extends the following concepts:

.. _model-account.dunning.fee:

Dunning Fee
===========

A *Dunning Fee* defines how to calculate and post a fee for a `Dunning
<account_dunning:model-account.dunning>`.

.. seealso::

   The Dunning Fees are available from the main menu item:

      |Financial --> Configuration --> Dunnings --> Fees|__

      .. |Financial --> Configuration --> Dunnings --> Fees| replace:: :menuselection:`Financial --> Configuration --> Dunnings --> Fees`
      __ https://demo.tryton.org/model/account.dunning.fee

.. _model-account.dunning.level:

Dunning Level
=============

The *Dunning Level* can be set up with a `Fee <model-account.dunning.fee>` that
will be applied when the `Dunning <account_dunning:model-account.dunning>`
reaches that *Level*.

.. seealso::

   The `Dunning Level <account_dunning:model-account.dunning.level>` concept is
   introduced by the :doc:`Account Dunning Module <account_dunning:index>`.

.. _model-account.dunning:

Dunning
=======

The *Dunning* is extended to list the fees that were applied to it.

.. seealso::

   The `Dunning <account_dunning:model-account.dunning>` concept is introduced
   by the :doc:`Account Dunning Module <account_dunning:index>`.

Reports
-------

.. _report.account.dunning.letter:

Dunning Letter
^^^^^^^^^^^^^^

The *Dunning Letter* is extended to render the total amount of fees applied to
each `Dunning <account_dunning:model-account.dunning>`.

.. seealso::

   The `Dunning Letter <account_dunning_letter:report-account.dunning.letter>`
   report is introduced by the :doc:`Account Dunning Letter Module
   <account_dunning_letter:index>`.
