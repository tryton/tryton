******
Design
******

The *Account Statement Module* introduces the following concepts:

.. _model-account.statement:

Statement
=========

The *Statement* concept groups together lines that represent entries in a
`Journal <model-account.statement.journal>`.
These lines contain, among other information, the date, amount, `party
<party:model-party.party>` and `account <account:model-account.account>`.

A statement may also contain a list of origins each of these holds a single
line from the raw information that was imported.

A statement progresses through several different states until it is either
posted or cancelled.

.. seealso::

   Statements can be found by opening the main menu item:

      |Financial --> Statements --> Statements|__

      .. |Financial --> Statements --> Statements| replace:: :menuselection:`Financial --> Statements --> Statements`
      __ https://demo.tryton.org/model/account.statement

Reports
-------

.. _report-account.statement:

Statement Report
^^^^^^^^^^^^^^^^

The *Statement Report* is a document that can be printed out that contains all
the relevant information about each statement, including the lines.

Wizards
-------

.. _wizard-account.statement.import:

Import Statement
^^^^^^^^^^^^^^^^

The *Import Statement* wizard creates `Statements <model-account.statement>`
from one of the supported file formats.
The raw lines from the file are stored as a list of origins on the statement.

.. seealso::

   Import Statement can be launch by opening the main menu item:

      |Financial --> Statements --> Import Statement|__

      .. |Financial --> Statements --> Import Statement| replace:: :menuselection:`Financial --> Statements --> Import Statement`
      __ https://demo.tryton.org/wizard/account.statement.import


.. _wizard-account.statement.reconcile:

Reconcile Statement
^^^^^^^^^^^^^^^^^^^

The *Reconcile Statement* wizard launches the `Reconcile Accounts
<account:wizard-account.reconcile>` wizard on the `Account Move Lines
<account:model-account.move.line>` created by the `Statement
<model-account.statement>`.

.. _model-account.statement.line.group:

Line Group
==========

The *Line Group* displays the grouping of statement lines that was created
at the point when the `Statement <model-account.statement>` was validated.

.. seealso::

   Line Groups can be found by opening the main menu item:

      |Financial --> Statements --> Statements --> Line Groups|__

      .. |Financial --> Statements --> Statements --> Line Groups| replace:: :menuselection:`Financial --> Statements --> Statements --> Line Groups`
      __ https://demo.tryton.org/model/account.statement.line.group

.. _model-account.statement.journal:

Statement Journal
=================

A *Statement Journal* represents a `Statement <model-account.statement>` book.
Among other things it defines how the statements must be validated.

.. seealso::

   Statement Journals can be found by opening the main menu item:

      |Financial --> Configuration --> Statements --> Statement Journals|__

      .. |Financial --> Configuration --> Statements --> Statement Journals| replace:: :menuselection:`Financial --> Configuration --> Statements --> Statement Journals`
      __ https://demo.tryton.org/model/account.statement.journal
