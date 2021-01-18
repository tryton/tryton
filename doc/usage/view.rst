.. _Viewing journal entries:

Viewing journal entries
=======================

In Tryton there are plenty of different ways of getting information about
the `journal entries`_ that record your
`Company's <company:model-company.company>` accounting transactions.

Each journal entry is represented by an `Account Move <model-account.move>`.
These account moves, and the `Account Move Lines <model-account.move.line>`
that make them up, can be found by:

* Using the items in the [:menuselection:`Financial --> Entries`] main menu
  item.
* `Viewing your chart of accounts data` and opening the accounts.
* `Using the general ledger` and opening the accounts.
* `Using the balance sheet` and opening the lines and then accounts.
* `Using the income statement` and opening the lines and then accounts.

.. tip::

    Account moves that are created by, or relate to, other documents or items
    on you Tryton system can also often be found from those documents or items.

.. _journal entries: https://en.wikipedia.org/wiki/Journal_entry

.. _Viewing your chart of accounts data:

Viewing your chart of accounts data
===================================

The `Open Chart of Accounts <wizard-account.open_chart>` wizard can be run
from the main menu to open your chart of accounts.

This provides a structured view of all the `Accounts <model-account.account>`
that form your `Company's <company:model-company.company>` accounts.

.. tip::

    Each account can be opened to show the
    `Account Move Lines <model-account.move.line>` that contributed to the
    debits and credits shown for that account.

.. _Viewing your tax code data:

Viewing your tax code data
==========================

The `Open Chart of Tax Codes <wizard-account.tax.code.open_chart>` wizard can
be run from the main menu to open your chart of tax codes.

From here you are able to see data about what `Taxes <model-account.tax>` have
been applied and what amounts these were based on.
The `Tax Codes <model-account.tax.code>` are normally structured so that you
can find the data that you need to do your tax reporting.

.. tip::

    Each tax code can be opened to show the
    `Tax Lines <model-account.tax.line>` that contribute to the tax code's
    amount.
