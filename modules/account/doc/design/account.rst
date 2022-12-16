.. _model-account.account:

Account
=======

In Tryton the *Account* concept is used to represent the different accounts
that make up the `Company's <company:model-company.company>` chart of accounts.
These accounts are commonly organised into a structure, with each account
having a single parent and zero or more sub accounts.

The balance of an account is made up from all the credits and debits into
the account and its sub accounts.
These values are in the company's
`Currency <currency:model-currency.currency>`, but a second currency can be
used on accounts that record transactions that happen in a different currency.

Each account has an `Account Type <model-account.account.type>` which
defines some additional properties of the account.
A second type can be specified for accounts whose type depends on whether they
have a credit or debit balance.

Only accounts that are not closed can be used as a source or destination for
`Account Moves <model-account.move>`.

Tryton will only try and reconcile
`Account Move Lines <model-account.move.line>` in accounts that are correctly
marked when `Reconciling <wizard-account.reconcile>` accounts.

In Tryton a *deferral* account is any account that appears on a company's
balance sheet, or is not shown on any reports.
The amounts in these accounts are carried forward to subsequent
`Fiscal Years <model-account.fiscalyear>`, and are stored using the
`Account Deferral <model-account.account.deferral>` concept.

.. seealso::

   A list of the accounts is available via the main menu item:

      |Financial --> Configuration --> General Account --> Accounts|__

      .. |Financial --> Configuration --> General Account --> Accounts| replace:: :menuselection:`Financial --> Configuration --> General Account --> Accounts`
      __ https://demo.tryton.org/model/account.account

   Accounts can be created from
   `Account Templates <model-account.account.template>`.

Wizards
-------

.. _wizard-account.open_chart:

Open Chart of Accounts
^^^^^^^^^^^^^^^^^^^^^^

This wizard opens the company's chart of accounts.

.. seealso::

   The chart of accounts can be opened using the main menu item:

      :menuselection:`Financial --> Charts --> Open Chart of Accounts`

.. _model-account.account.type:

Account Type
============

The *Account Type* concept defines the structure of the
`Company's <company:model-company.company>` accounting reports.
It defines whether the account type appears on the balance sheet or income
statement, and has a set of properties that indicate what any
`Accounts <model-account.account>` of this type can be used for.

When used as the balance sheet or income statement the amount shown for the
account type includes the amounts from all the accounts of that type and
includes the amounts from all of its children.

The amounts from accounts that also have a debit type are only ever included
in either the account's type, or its debit type, depending on whether the
accounts balance is in credit, or debit, respectively.

.. seealso::

   The list of account types can be found by opening the main menu item:

      |Financial --> Configuration --> General Account --> Account Types|__

      .. |Financial --> Configuration --> General Account --> Account Types| replace:: :menuselection:`Financial --> Configuration --> General Account --> Account Types`
      __ https://demo.tryton.org/model/account.account.type

   Accounts Types can be created from
   `Account Type Templates <model-account.account.type.template>`.

Reports
-------

.. _report-account.account.type.statement:

Statement
^^^^^^^^^

The *Statement* report is used to get a printed copy of the open parts
of the balance sheet and income statements.

.. _model-account.account.party:

Account Party
=============

The *Account Party* concept is used to show the balances, and credits and
debits, for each `Party <party:model-party.party>` in an
`Account <model-account.account>`.

.. _model-account.account.deferral:

Account Deferral
================

The *Account Deferral* concept stores, by `Account <model-account.account>`,
any amounts that need to be carried forward to the next
`Fiscal Year <model-account.fiscalyear>`.
The data that gets stored here is managed automatically when fiscal years
are closed or re-opened.

.. _model-account.general_ledger.account:

General Ledger Account
======================

The list of *General Ledger Accounts* gives a top level view of a
`Company's <company:model-company.company>` general ledger.
For the specified period of time, it provides a summary of the debits and
credits into the `Accounts <model-account.account>`, and the starting and
ending values for the debits, credits and account balances.

.. seealso::

   The company's general ledger can be opened using the main menu item:

      |Financial --> Reporting --> General Ledger|__

      .. |Financial --> Reporting --> General Ledger| replace:: :menuselection:`Financial --> Reporting --> General Ledger`
      __ https://demo.tryton.org/model/account.general_ledger.account;context_model=account.general_ledger.account.context

Reports
-------

.. _report-account.general_ledger:

General Ledger
^^^^^^^^^^^^^^

For each selected *General Ledger Account* the *General Ledger* report provides
a detailed list of all of the transactions that occurred during the specified
period of time.
These are summed up for each general ledger account, and the account balance
is also shown.

.. _report-account.trial_balance:

Trial Balance
^^^^^^^^^^^^^

The *Trial Balance* report allows a hard copy of the *General Ledger Account's*
summaries to be printed out.
It lists each selected general ledger account along with its start and end
balances and total debits and credits.

.. _model-account.general_ledger.account.party:

General Ledger Account Party
============================

The *General Ledger Account Party* concept provides the same information as the
`General Ledger Account <model-account.general_ledger.account>`, but grouped
by `Party <party:model-party.party>`.

It can be used to show the information that is normally found in a `Debtors
or Creditors Ledger`_.

.. _Debtors or Creditors Ledger: https://en.wikipedia.org/wiki/Ledger#Types_on_the_basis_of_purpose

.. _model-account.aged_balance:

Aged Balance
============

The *Aged Balance* shows a breakdown of how overdue payments are both to and
from customers and suppliers.
It allows the length of some terms to be set and then, for each
`Party <party:model-party.party>`, groups the payment amounts into the
appropriate term based on the maturity date from the payment's
`Account Move Line <model-account.move.line>`.
A payment amount appears in the first term it is equal to or more overdue than.

Reports
-------

.. _report-account.aged_balance:

Aged Balance
^^^^^^^^^^^^

The *Aged Balance* report lets the user get a hard copy of the selected terms
and aged balances.
