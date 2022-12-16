========================
Analytic Budget Scenario
========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> today = dt.date.today()

Activate the analytic_budget module::

    >>> config = activate_modules('analytic_budget')

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> Budget = Model.get('analytic_account.budget')
    >>> BudgetLine = Model.get('analytic_account.budget.line')
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
    >>> next_period = fiscalyear.periods[1]

Create a chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create the analytic accounts::

    >>> root = AnalyticAccount(type='root', name="Root")
    >>> root.save()
    >>> analytic_account = AnalyticAccount(
    ...     root=root, parent=root, name="Analytic")
    >>> analytic_account.save()
    >>> other_analytic_account = AnalyticAccount(
    ...     root=root, parent=root, name="Other Analytic")
    >>> other_analytic_account.save()

Create the parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create a budget::

    >>> budget = Budget()
    >>> budget.name = 'Budget'
    >>> budget.root = root
    >>> budget.start_date = period.start_date
    >>> budget.end_date = period.end_date
    >>> budget.click('update_lines')
    >>> len(budget.lines)
    2

    >>> analytic_budget, = BudgetLine.find(
    ...     [('account', '=', analytic_account.id)])
    >>> analytic_budget.sequence = 1
    >>> analytic_budget.amount = Decimal(-70)
    >>> analytic_budget.save()
    >>> other_analytic_budget, = BudgetLine.find(
    ...     [('account', '=', other_analytic_account.id)])
    >>> other_analytic_budget.sequence = 2
    >>> other_analytic_budget.amount = Decimal(-50)
    >>> other_analytic_budget.save()

    >>> budget.click('update_lines')
    >>> len(budget.lines)
    2

Create moves to test the budget::

    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(100)
    >>> analytic_line = line.analytic_lines.new()
    >>> analytic_line.credit = Decimal(60)
    >>> analytic_line.account = analytic_account
    >>> analytic_line = line.analytic_lines.new()
    >>> analytic_line.credit = Decimal(40)
    >>> analytic_line.account = other_analytic_account
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(100)
    >>> line.party = customer
    >>> move.click('post')

Check actual amount the budget::

    >>> analytic_budget.total_amount
    Decimal('-70.00')
    >>> analytic_budget.actual_amount
    Decimal('-60.00')
    >>> analytic_budget.percentage
    Decimal('0.8571')
    >>> other_analytic_budget.total_amount
    Decimal('-50.00')
    >>> other_analytic_budget.actual_amount
    Decimal('-40.00')
    >>> other_analytic_budget.percentage
    Decimal('0.8000')

Copy the budget without amounts::

    >>> copy_budget = Wizard('analytic_account.budget.copy', [budget])
    >>> copy_budget.form.start_date = next_period.start_date
    >>> copy_budget.form.end_date = next_period.end_date
    >>> copy_budget.form.factor = Decimal('1.2')
    >>> copy_budget.execute('copy')
    >>> new_budget, = copy_budget.actions[0]
    >>> new_budget.start_date == next_period.start_date
    True
    >>> new_budget.end_date == next_period.end_date
    True
    >>> analytic_budget, other_analytic_budget = new_budget.lines
    >>> analytic_budget.total_amount
    Decimal('-84.00')
    >>> analytic_budget.actual_amount
    Decimal('0.00')
    >>> analytic_budget.percentage
    Decimal('0.0000')
