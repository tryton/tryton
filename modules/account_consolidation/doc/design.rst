******
Design
******

The *Account Consolidation Module* introduces the following concepts:

.. _model-account.consolidation:

Account Consolidation
=====================

The *Account Consolidation* concept defines the structure of the accounting
reports for multiple `Companies <company:model-company.company>`.
It groups `Account types <account:model-account.account.type>` of different
companies on a consolidated balance sheet or income statement.

When used as the consolidated balance sheet or income statement the amount
shown includes the amounts of all the account types of the record for all the
selected companies.

.. seealso::

   The list of account consolidation can be found by opening the main menu item:

      |Financial --> Configuration --> General Account --> Account Consolidations|__

      .. |Financial --> Configuration --> General Account --> Account Consolidations| replace:: :menuselection:`Financial --> Configuration --> General Account --> Account Consolidations`
      __ https://demo.tryton.org/model/account.consolidation


Reports
-------

.. _report-account.consolidation.statement:

Statement
^^^^^^^^^

The *Statement* report is used to get a printed copy of the open parts of the
consolidated balance sheet and income statements.
