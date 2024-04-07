******
Design
******

The *Account Export Module* introduces the following concepts:

.. _model-account.move.export:

Account Move Export
===================

An *Account Move Export* groups posted `Moves <account:model-account.move>` to
be exported to an external accounting software.
When an export is created in draft state, the :guilabel:`Select Moves` button
can be clicked to fill it with all posted moves that are not yet exported.
Then the export is moved to waiting state and generates the required data based
on its type.
And finally the export is marked as done as final state when data has been
imported into the external software.

.. seealso::

   Account Move Exports are found by opening the main menu item:

      |Financial --> Processing --> Move Exports|__

      .. |Financial --> Processing --> Move Exports| replace:: :menuselection:`Financial --> Processing --> Move Exports`
      __ https://demo.tryton.org/model/account.move.export
