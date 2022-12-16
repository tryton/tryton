=======================
Account Budget Scenario
=======================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('account_budget')

    >>> Account = Model.get('account.account')
    >>> Budget = Model.get('account.budget')
    >>> BudgetLine = Model.get('account.budget.line')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Create a company::

    >>> _ = create_company()
    >>> company = get_company()

Create a fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]
    >>> next_fiscalyear = create_fiscalyear(
    ...     company, fiscalyear.end_date + dt.timedelta(days=1))
    >>> next_fiscalyear.click('create_period')

Create a chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create the parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create a budget::

    >>> budget = Budget()
    >>> budget.name = 'Budget'
    >>> budget.fiscalyear = fiscalyear
    >>> budget.click('update_lines')
    >>> len(budget.lines)
    5

    >>> revenue_budget, = BudgetLine.find(
    ...     [('account', '=', accounts['revenue'].id)])
    >>> revenue_budget.amount = Decimal(-150)
    >>> revenue_budget.save()
    >>> expense_budget, = BudgetLine.find(
    ...     [('account', '=', accounts['expense'].id)])
    >>> expense_budget.amount = Decimal(50)
    >>> expense_budget.save()

    >>> budget.click('update_lines')
    >>> len(budget.lines)
    5

Create moves to test the budget::

    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_expense, = Journal.find([
    ...         ('code', '=', 'EXP'),
    ...         ])
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(130)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(130)
    >>> line.party = customer
    >>> move.click('post')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_expense
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['expense']
    >>> line.debit = Decimal(60)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.credit = Decimal(60)
    >>> line.party = supplier
    >>> move.click('post')

Check actual amount of the budget::

    >>> pl_budget, = budget.root_lines
    >>> pl_budget.total_amount
    Decimal('-100.00')
    >>> pl_budget.actual_amount
    Decimal('-70.00')
    >>> pl_budget.percentage
    Decimal('0.7000')
    >>> revenue_budget.total_amount
    Decimal('-150.00')
    >>> revenue_budget.actual_amount
    Decimal('-130.00')
    >>> revenue_budget.percentage
    Decimal('0.8667')
    >>> expense_budget.total_amount
    Decimal('50.00')
    >>> expense_budget.actual_amount
    Decimal('60.00')
    >>> expense_budget.percentage
    Decimal('1.2000')

Create periods::

    >>> create_periods = Wizard(
    ...     'account.budget.line.create_periods', [pl_budget])
    >>> create_periods.execute('create_periods')
    >>> revenue_budget, expense_budget = pl_budget.children
    >>> len(pl_budget.periods)
    12
    >>> all(p.total_amount == Decimal('-8.33') for p in pl_budget.periods)
    True
    >>> len(revenue_budget.periods)
    12
    >>> all(p.total_amount == Decimal('-12.50') for p in revenue_budget.periods)
    True
    >>> len(expense_budget.periods)
    12
    >>> all(p.total_amount == Decimal('4.16') for p in expense_budget.periods)
    True

Check the budget's periods::

    >>> pl_budget.periods[0].actual_amount
    Decimal('-70.00')
    >>> pl_budget.periods[0].percentage
    Decimal('8.4034')
    >>> pl_budget.periods[1].actual_amount
    Decimal('0.00')
    >>> pl_budget.periods[1].percentage
    Decimal('0.0000')
    >>> revenue_budget.periods[0].actual_amount
    Decimal('-130.00')
    >>> revenue_budget.periods[0].percentage
    Decimal('10.4000')
    >>> revenue_budget.periods[1].actual_amount
    Decimal('0.00')
    >>> revenue_budget.periods[1].percentage
    Decimal('0.0000')
    >>> expense_budget.periods[0].actual_amount
    Decimal('60.00')
    >>> expense_budget.periods[0].percentage
    Decimal('14.4231')
    >>> expense_budget.periods[1].actual_amount
    Decimal('0.00')
    >>> expense_budget.periods[1].percentage
    Decimal('0.0000')

Try to set invalid ratio::

    >>> period = pl_budget.periods[0]
    >>> period.ratio = Decimal('0.1')
    >>> budget.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    BudgetValidationError: ...
    >>> budget.reload()

Copy the budget without amounts::

    >>> copy_budget = Wizard('account.budget.copy', [budget])
    >>> copy_budget.form.name
    'Budget'
    >>> copy_budget.form.name = 'New Budget'
    >>> copy_budget.form.fiscalyear = next_fiscalyear
    >>> copy_budget.form.factor = Decimal('1.25')
    >>> copy_budget.execute('copy')
    >>> new_budget, = copy_budget.actions[0]
    >>> new_budget.name
    'New Budget'
    >>> new_pl_budget, = new_budget.root_lines
    >>> new_pl_budget.total_amount
    Decimal('-125.00')
    >>> new_pl_budget.actual_amount
    Decimal('0.00')
    >>> new_pl_budget.percentage
    Decimal('0.0000')
    >>> len(new_pl_budget.periods)
    0
