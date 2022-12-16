.. _model-account.journal:

Journal
=======

A *Journal* represents a book of original entry from traditional manual
accounting.
In Tryton it allows `Account Moves <model-account.move>` of the same class
to be grouped together.
Every account move gets associated with a journal, and the journal defines
what sequence is then used to number the account move.

Among the journal's properties is a type.
This limits where the journal can be used.

.. seealso::

   The journals can be found by opening the main menu item:

      |Financial --> Configuration --> Journals --> Journals|__

      .. |Financial --> Configuration --> Journals --> Journals| replace:: :menuselection:`Financial --> Configuration --> Journals --> Journals`
      __ https://demo.tryton.org/model/account.journal

Wizards
-------

.. _wizard-account.move.open_journal:

Open Journal
^^^^^^^^^^^^

The *Open Journal* wizard opens an editable list which can be used to quickly
enter in journal entries for a specific journal and
`Period <model-account.period>`.

.. seealso::

   The wizard can be started by using the main menu item:

      :menuselection:`Financial --> Entries --> Open Journal`

.. _model-account.journal.period:

Journal Period
==============

For each `Company <company:model-company.company>`, a *Journal Period* links
together the concepts of a `Journal <model-account.journal>`, and an accounting
`Period <model-account.period>`.
Each journal period is created automatically when the first
`Account Move <model-account.move>` is created in the journal and period.
It provides a way of partially closing a period one journal at a time.

.. seealso::

   The company's journal periods can be listed by opening the main menu item:

      |Financial --> Reporting --> Journals - Periods|__

      .. |Financial --> Reporting --> Journals - Periods| replace:: :menuselection:`Financial --> Reporting --> Journals - Periods`
      __ https://demo.tryton.org/model/account.journal.period

   The company's open journal periods can be found using the main menu item:

      :menuselection:`Financial --> Entries --> Journals - Periods`
