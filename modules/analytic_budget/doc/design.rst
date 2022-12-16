******
Design
******

.. _model-analytic_account.budget:

Analytic Budget
===============

An *Analytic Budget* is used to define a financial plan for a set of
:doc:`Analytic Accounts <analytic_account:index>` over a defined period of time
and for a specific `Company <company:model-company.company>`.

A budget is made up from budget lines which define the budgeted amount for an
:doc:`Analytic Account <analytic_account:index>`.
These lines can be grouped under another line to form a tree structure that
sums up the amounts.

The actual amount of the budget lines is calculated from the debits and credits
that are made to the budget’s analytic accounts.

.. seealso::

   Analytic budgets can be managed from the main menu item:

      |Financial --> Budgets --> Analytic Budgets|__

      .. |Financial --> Budgets --> Analytic Budgets| replace:: :menuselection:`Financial --> Budgets --> Analytic Budgets`
      __ https://demo.tryton.org/model/analytic_account.budget

   The actual amounts for the budgets can be found from the main menu item:

      :menuselection:`Financial --> Reporting --> Analytic Budgets`

Wizards
-------

.. _wizard-analytic_account.budget.copy:

Copy Budget
^^^^^^^^^^^

The *Copy Budget* wizard is used to copy an entire budget.
It allows the period and amounts in the copied budget to be changed.
