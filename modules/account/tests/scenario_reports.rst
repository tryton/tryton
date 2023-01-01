========================
Account Reports Scenario
========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company, today)
    >>> fiscalyear.click('create_period')
    >>> periods = fiscalyear.periods
    >>> period_1, period_3, period_5 = periods[0], periods[2], periods[4]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create a child account::

    >>> _ = revenue.childs.new()
    >>> revenue.save()
    >>> child_revenue, = revenue.childs

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create a moves::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])
    >>> move = Move()
    >>> move.period = period_3
    >>> move.journal = journal_revenue
    >>> move.date = period_3.start_date
    >>> line = move.lines.new()
    >>> line.account = child_revenue
    >>> line.credit = Decimal(10)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(10)
    >>> line.party = party
    >>> move.save()

    >>> move = Move()
    >>> move.period = period_5
    >>> move.journal = journal_cash
    >>> move.date = period_5.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(10)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(10)
    >>> line.party = party
    >>> move.save()

Print some reports::

    >>> GeneralLedgerAccount = Model.get('account.general_ledger.account')
    >>> GeneralLedgerAccountParty = Model.get(
    ...     'account.general_ledger.account.party')
    >>> gl_accounts = GeneralLedgerAccount.find([])
    >>> _ = [(l.balance, l.party_required) for gl in gl_accounts
    ...     for l in gl.lines]

    >>> general_ledger = Report('account.general_ledger', context={
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     })
    >>> _ = general_ledger.execute(gl_accounts)

    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     }
    >>> with config.set_context(context):
    ...     gl_child_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', child_revenue.id),
    ...           ])
    ...     gl_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', revenue.id),
    ...           ])
    ...     glp_receivable, = GeneralLedgerAccountParty.find([
    ...             ('account', '=', receivable.id),
    ...             ('party', '=', party.id),
    ...             ])
    >>> gl_child_revenue.start_balance
    Decimal('0.00')
    >>> gl_child_revenue.credit
    Decimal('10.00')
    >>> gl_child_revenue.debit
    Decimal('0.00')
    >>> gl_child_revenue.end_balance
    Decimal('-10.00')
    >>> gl_child_revenue.line_count
    1
    >>> gl_revenue.start_balance
    Decimal('0.00')
    >>> gl_revenue.credit
    Decimal('0.00')
    >>> gl_revenue.debit
    Decimal('0.00')
    >>> gl_revenue.end_balance
    Decimal('-10.00')
    >>> gl_revenue.line_count
    0
    >>> glp_receivable.start_balance
    Decimal('0.00')
    >>> glp_receivable.credit
    Decimal('10.00')
    >>> glp_receivable.debit
    Decimal('10.00')
    >>> glp_receivable.end_balance
    Decimal('0.00')
    >>> glp_receivable.line_count
    2

    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'from_date': period_1.start_date,
    ...     'to_date': period_3.end_date,
    ...     }
    >>> with config.set_context(context):
    ...     gl_child_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', child_revenue.id),
    ...           ])
    ...     gl_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', revenue.id),
    ...           ])
    ...     glp_receivable, = GeneralLedgerAccountParty.find([
    ...             ('account', '=', receivable.id),
    ...             ('party', '=', party.id),
    ...             ])
    >>> gl_child_revenue.start_balance
    Decimal('0.00')
    >>> gl_child_revenue.credit
    Decimal('10.00')
    >>> gl_child_revenue.debit
    Decimal('0.00')
    >>> gl_child_revenue.end_balance
    Decimal('-10.00')
    >>> gl_child_revenue.line_count
    1
    >>> gl_revenue.start_balance
    Decimal('0.00')
    >>> gl_revenue.credit
    Decimal('0.00')
    >>> gl_revenue.debit
    Decimal('0.00')
    >>> gl_revenue.end_balance
    Decimal('-10.00')
    >>> gl_revenue.line_count
    0
    >>> glp_receivable.start_balance
    Decimal('0.00')
    >>> glp_receivable.credit
    Decimal('0.00')
    >>> glp_receivable.debit
    Decimal('10.00')
    >>> glp_receivable.end_balance
    Decimal('10.00')
    >>> glp_receivable.line_count
    1

    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'start_period': period_3.id,
    ...     }
    >>> with config.set_context(context):
    ...     gl_child_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', child_revenue.id),
    ...           ])
    ...     gl_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', revenue.id),
    ...           ])
    >>> gl_child_revenue.start_balance
    Decimal('0.00')
    >>> gl_child_revenue.credit
    Decimal('10.00')
    >>> gl_child_revenue.debit
    Decimal('0.00')
    >>> gl_child_revenue.end_balance
    Decimal('-10.00')
    >>> gl_child_revenue.line_count
    1
    >>> gl_revenue.start_balance
    Decimal('0.00')
    >>> gl_revenue.credit
    Decimal('0.00')
    >>> gl_revenue.debit
    Decimal('0.00')
    >>> gl_revenue.end_balance
    Decimal('-10.00')
    >>> gl_revenue.line_count
    0

    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'start_period': period_5.id,
    ...     }
    >>> with config.set_context(context):
    ...     gl_child_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', child_revenue.id),
    ...           ])
    ...     gl_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', revenue.id),
    ...           ])
    >>> gl_child_revenue.start_balance
    Decimal('-10.00')
    >>> gl_child_revenue.credit
    Decimal('0.00')
    >>> gl_child_revenue.debit
    Decimal('0.00')
    >>> gl_child_revenue.end_balance
    Decimal('-10.00')
    >>> gl_child_revenue.line_count
    0
    >>> gl_revenue.start_balance
    Decimal('-10.00')
    >>> gl_revenue.credit
    Decimal('0.00')
    >>> gl_revenue.debit
    Decimal('0.00')
    >>> gl_revenue.end_balance
    Decimal('-10.00')
    >>> gl_revenue.line_count
    0

    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'from_date': period_3.start_date,
    ...     }
    >>> with config.set_context(context):
    ...     gl_child_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', child_revenue.id),
    ...           ])
    ...     gl_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', revenue.id),
    ...           ])
    >>> gl_child_revenue.start_balance
    Decimal('0.00')
    >>> gl_child_revenue.credit
    Decimal('10.00')
    >>> gl_child_revenue.debit
    Decimal('0.00')
    >>> gl_child_revenue.end_balance
    Decimal('-10.00')
    >>> gl_child_revenue.line_count
    1
    >>> gl_revenue.start_balance
    Decimal('0.00')
    >>> gl_revenue.credit
    Decimal('0.00')
    >>> gl_revenue.debit
    Decimal('0.00')
    >>> gl_revenue.end_balance
    Decimal('-10.00')
    >>> gl_revenue.line_count
    0

    >>> context = {
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     'from_date': period_5.start_date,
    ...     }
    >>> with config.set_context(context):
    ...     gl_child_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', child_revenue.id),
    ...           ])
    ...     gl_revenue, = GeneralLedgerAccount.find([
    ...           ('account', '=', revenue.id),
    ...           ])
    >>> gl_child_revenue.start_balance
    Decimal('-10.00')
    >>> gl_child_revenue.credit
    Decimal('0.00')
    >>> gl_child_revenue.debit
    Decimal('0.00')
    >>> gl_child_revenue.end_balance
    Decimal('-10.00')
    >>> gl_child_revenue.line_count
    0
    >>> gl_revenue.start_balance
    Decimal('-10.00')
    >>> gl_revenue.credit
    Decimal('0.00')
    >>> gl_revenue.debit
    Decimal('0.00')
    >>> gl_revenue.end_balance
    Decimal('-10.00')
    >>> gl_revenue.line_count
    0

    >>> trial_balance = Report('account.trial_balance', context={
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     })
    >>> _ = trial_balance.execute(gl_accounts)

    >>> Type = Model.get('account.account.type')
    >>> statement = Report('account.account.type.statement')
    >>> _ = statement.execute(Type.find([]))

    >>> AgedBalance = Model.get('account.aged_balance')
    >>> context = {
    ...     'company': company.id,
    ...     'type': 'customer',
    ...     'date': today,
    ...     'term1': 30,
    ...     'term2': 60,
    ...     'term3': 90,
    ...     'unit': 'day',
    ...     }
    >>> with config.set_context(context):
    ...     aged_balances = AgedBalance.find([])

    >>> aged_balance = Report('account.aged_balance', context=context)
    >>> _ = aged_balance.execute(aged_balances)

    >>> general_journal = Report('account.move.general_journal')
    >>> _ = general_journal.execute(Move.find([]))

    >>> with config.set_context(
    ...         start_date=period_5.start_date,
    ...         end_date=period_5.end_date):
    ...     journal_cash = Journal(journal_cash.id)
    >>> journal_cash.credit
    Decimal('0.00')
    >>> journal_cash.debit
    Decimal('10.00')
    >>> journal_cash.balance
    Decimal('10.00')
