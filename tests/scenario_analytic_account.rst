=========================
Analytic Account Scenario
=========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('analytic_account')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> Journal = Model.get('account.journal')
    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
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
    >>> rule1 = AnalyticRule(company=company, account=expense)
    >>> entry, = rule1.analytic_accounts
    >>> entry.account = analytic_account
    >>> rule1.save()
    >>> rule2 = AnalyticRule(company=company, account=revenue)
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

Cancel Move::

    >>> cancel_move = Wizard('account.move.cancel', [move])
    >>> cancel_move.form.description = 'Cancel'
    >>> cancel_move.execute('cancel')
    >>> move.reload()
    >>> line, = [l for l in move.lines if l.account == receivable]
    >>> bool(line.reconciliation)
    True
    >>> cancel_move, = [l.move for l in line.reconciliation.lines
    ...     if l.move != move]
    >>> cancel_move.origin == move
    True
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('42.00')
    >>> analytic_account.debit
    Decimal('42.00')

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
    >>> analytic_line.account == analytic_account2
    True
    >>> analytic_line.credit
    Decimal('73')
    >>> analytic_line.date == analytic_line.move_line.date
    True

Prepare to balance non-deferral accounts::

    >>> Sequence = Model.get('ir.sequence')
    >>> Period = Model.get('account.period')
    >>> AccountType = Model.get('account.account.type')
    >>> Account = Model.get('account.account')
    >>> journal_sequence, = Sequence.find([('code', '=', 'account.journal')])
    >>> journal_closing = Journal()
    >>> journal_closing.code = 'CLO'
    >>> journal_closing.type = 'situation'
    >>> journal_closing.name = "Closing"
    >>> journal_closing.sequence = journal_sequence
    >>> journal_closing.save()
    >>> period_closing = Period()
    >>> period_closing.name = "Closing"
    >>> period_closing.type = 'adjustment'
    >>> period_closing.fiscalyear = fiscalyear
    >>> period_closing.start_date = fiscalyear.end_date
    >>> period_closing.end_date = fiscalyear.end_date
    >>> period_closing.save()
    >>> equity, = AccountType.find([('name', '=', 'Equity')])
    >>> account_pl = Account()
    >>> account_pl.name = 'P&L'
    >>> account_pl.type = equity
    >>> account_pl.parent = revenue.parent
    >>> account_pl.save()

Balance non-deferral accounts::

    >>> balance_non_deferral = Wizard('account.fiscalyear.balance_non_deferral')
    >>> balance_non_deferral.form.fiscalyear = fiscalyear
    >>> balance_non_deferral.form.journal = journal_closing
    >>> balance_non_deferral.form.period = period_closing
    >>> balance_non_deferral.form.credit_account = account_pl
    >>> balance_non_deferral.form.debit_account = account_pl
    >>> balance_non_deferral.execute('balance')
    >>> move, = Move.find([
    ...     ('state', '=', 'draft'),
    ...     ('journal', '=', journal_closing.id),
    ...     ])
    >>> move.click('post')
    >>> [l for l in move.lines if l.analytic_lines]
    []
