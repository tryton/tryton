=========================
Analytic Account Scenario
=========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('analytic_account', create_company, create_chart)

    >>> Reconciliation = Model.get('account.move.reconciliation')
    >>> Journal = Model.get('account.journal')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])

Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()
    >>> analytic_account2 = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic 2')
    >>> analytic_account2.save()

Create analytic rules::

    >>> AnalyticRule = Model.get('analytic_account.rule')
    >>> rule1 = AnalyticRule(account=expense)
    >>> entry, = rule1.analytic_accounts
    >>> entry.account = analytic_account
    >>> rule1.save()
    >>> rule2 = AnalyticRule(account=revenue)
    >>> entry, = rule2.analytic_accounts
    >>> entry.account = analytic_account2
    >>> rule2.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create Move analytic accounts::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(42)
    >>> analytic_line = line.analytic_lines.new()
    >>> analytic_line.credit = line.credit
    >>> analytic_line.account = analytic_account
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.click('post')
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('42.00')
    >>> analytic_account.debit
    Decimal('0.00')

Cancel reversal move::

    >>> cancel_move = Wizard('account.move.cancel', [move])
    >>> cancel_move.form.description = 'Cancel'
    >>> cancel_move.execute('cancel')
    >>> move.reload()
    >>> line, = [l for l in move.lines if l.account == receivable]
    >>> bool(line.reconciliation)
    True
    >>> cancel_move, = [l.move for l in line.reconciliation.lines
    ...     if l.move != move]
    >>> assertEqual(cancel_move.origin, move)
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('42.00')
    >>> analytic_account.debit
    Decimal('42.00')

    >>> reconciliations = {
    ...     l.reconciliation for l in cancel_move.lines if l.reconciliation}
    >>> Reconciliation.delete(list(reconciliations))
    >>> cancel_move = Wizard('account.move.cancel', [cancel_move])
    >>> cancel_move.form.reversal = False
    >>> cancel_move.execute('cancel')
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('42.00')
    >>> analytic_account.debit
    Decimal('0.00')

Cancel move::

    >>> cancel_move = Wizard('account.move.cancel', [move])
    >>> cancel_move.form.description = 'Cancel'
    >>> cancel_move.form.reversal = False
    >>> cancel_move.execute('cancel')
    >>> move.reload()
    >>> line, = [l for l in move.lines if l.account == receivable]
    >>> bool(line.reconciliation)
    True
    >>> cancel_move, = [l.move for l in line.reconciliation.lines
    ...     if l.move != move]
    >>> assertEqual(cancel_move.origin, move)
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('0.00')
    >>> analytic_account.debit
    Decimal('0.00')

Create Move without analytic accounts::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(73)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(73)
    >>> line.party = customer

Check analytic lines are created on posting::

    >>> move.click('post')
    >>> line, = [l for l in move.lines if l.analytic_lines]
    >>> analytic_line, = line.analytic_lines
    >>> assertEqual(analytic_line.account, analytic_account2)
    >>> analytic_line.credit
    Decimal('73')
    >>> assertEqual(analytic_line.date, analytic_line.move_line.date)

Prepare to balance non-deferral accounts::

    >>> Period = Model.get('account.period')
    >>> AccountType = Model.get('account.account.type')
    >>> Account = Model.get('account.account')
    >>> journal_closing = Journal()
    >>> journal_closing.code = 'CLO'
    >>> journal_closing.type = 'situation'
    >>> journal_closing.name = "Closing"
    >>> journal_closing.save()
    >>> period_closing = Period()
    >>> period_closing.name = "Closing"
    >>> period_closing.type = 'adjustment'
    >>> period_closing.fiscalyear = fiscalyear
    >>> period_closing.start_date = fiscalyear.end_date
    >>> period_closing.end_date = fiscalyear.end_date
    >>> period_closing.save()
    >>> account_pl, = Account.find([('code', '=', '3.2.1')])

Balance non-deferral accounts::

    >>> balance_non_deferral = Wizard('account.fiscalyear.balance_non_deferral')
    >>> balance_non_deferral.form.fiscalyear = fiscalyear
    >>> balance_non_deferral.form.journal = journal_closing
    >>> balance_non_deferral.form.period = period_closing
    >>> balance_non_deferral.form.credit_account = account_pl
    >>> balance_non_deferral.form.debit_account = account_pl
    >>> balance_non_deferral.execute('balance')
    >>> move, = balance_non_deferral.actions[0]
    >>> move.click('post')
    >>> [l for l in move.lines if l.analytic_lines]
    []

Prevent changing root of account with entries::

    >>> root2 = AnalyticAccount(type='root', name="Root2")
    >>> root2.save()
    >>> analytic_account.root = root2
    >>> analytic_account.save()
    Traceback (most recent call last):
        ...
    AccessError: ...

    >>> analytic_account.reload()
    >>> analytic_account.code = "1"
    >>> analytic_account.save()
    >>> analytic_account.code
    '1'

Prevent changing type of analytic account with lines::

    >>> analytic_account.type = 'view'
    >>> analytic_account.save()
    Traceback (most recent call last):
        ...
    AccountValidationError: ...
