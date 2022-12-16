.. _Using the general ledger:

Using the general ledger
========================

Opening the [:menuselection:`Financial --> Reporting --> General Ledger`]
main menu item shows a list of the
`General Ledger Accounts <model-account.general_ledger.account>`.

You select the `Fiscal Year <model-account.fiscalyear>` and optionally the
starting and ending `Periods <model-account.period>`, or dates, to see data
for a specific time period.

Each general ledger account can be opened to provide a breakdown of the items
in that account.
This breakdown can be done to a
`Party <model-account.general_ledger.account.party>` or
`Account Move Line <model-account.move.line>` level.

A `General Ledger <report-account.general_ledger>` report, and a
`Trial Balance <report-account.trial_balance>` can also be printed from here.

.. tip::

   If you are only interested in accounts which have debits or credits you
   can use the filter to get a list of these by entering::

      Debit: !0 or Credit: !0

   Note: You should replace ``Debit`` and ``Credit`` with the correct names
   used in the language you are using Tryton in.

.. _Using the balance sheet:

Using the balance sheet
=======================

The [:menuselection:`Financial --> Reporting --> Balance Sheet`] shows the
`Company's <company:model-company.company>` assets and liabilities for the
chosen date.

You can use the :guilabel:`Comparison` checkbox to do a comparison of the
company's data for two different dates.

Opening a line from the balance sheet lists the
`Accounts <model-account.account>` that were included in the balance sheet's
line.
You can then open these accounts to get a list of the individual
`Account Move Lines <model-account.move.line>` that made up that account's
debits and credits.

.. _Using the income statement:

Using the income statement
==========================

The [:menuselection:`Financial --> Reporting --> Income Statement`] shows the
`Company's <company:model-company.company>` revenue and expenses for the
chosen period of time.

You can use the :guilabel:`Comparison` checkbox to do a comparison of the
company's data for two different periods of time.

Opening a line from the income statement lists the
`Accounts <model-account.account>` that were included in the income statement's
line.
You can then open these accounts to get a breakdown of the amount to a
`Party <model-account.general_ledger.account.party>` or
`Account Move Line <model-account.move.line>` level.

.. _Getting aged balances:

Getting aged balances
=====================

You can get an `Aged Balance <model-account.aged_balance>` for both suppliers
and customers.

You can change what unit of time is used for the terms, and length of each
term, to suit you needs.

You can also print a copy of the aged balances by using the
`Aged Balance <report-account.aged_balance>` report.
