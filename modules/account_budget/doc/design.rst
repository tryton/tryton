******
Design
******

.. _model-account.budget:

Budget
======

A *Budget*, in Tryton, is used to define a financial plan for a `Company
<company:model-company.company>` over a defined period of time.

A budget is made up from budget lines which define the budgeted amount for an
`Account <account:model-account.account>`.
These lines can be grouped together under another line to form a tree structure
that sums up the amounts.

The actual amount of the budget lines is calculated from the debits and credits
that are made to the budget's account.

To allow the budget to be monitored in stages a budget can be distributed over
the fiscal year's `Periods <account:model-account.period>`.

.. seealso::

   Budgets can be managed from the main menu item:

      |Financial --> Budgets --> Budgets|__

      .. |Financial --> Budgets --> Budgets| replace:: :menuselection:`Financial --> Budgets --> Budgets`
      __ https://demo.tryton.org/model/account.budget

   The actual amounts for the budgets can be found from the main menu item:

      :menuselection:`Financial --> Reporting --> Budgets`

Wizards
-------

.. _wizard-account.budget.copy:

Copy Budget
^^^^^^^^^^^

The *Copy Budget* wizard is used to copy an entire budget.
It allows the `Fiscal Year <account:model-account.fiscalyear>` and the amounts
to be changed in the copied budget.

.. _wizard-account.budget.line.create_periods:

Create Periods
^^^^^^^^^^^^^^

The *Create Periods* wizard makes it easy for the user to split the budget up
across `Periods <account:model-account.period>`. It divides the budget up by
using the selected method.
