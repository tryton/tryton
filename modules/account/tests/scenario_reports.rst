========================
Account Reports Scenario
========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'account'),
    ...         ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

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
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(10)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(10)
    >>> line.party = party
    >>> move.save()

Print some reports::

    >>> GeneralLedgerAccount = Model.get('account.general_ledger.account')
    >>> gl_accounts = GeneralLedgerAccount.find([])
    >>> _ = [(l.balance, l.party_required) for gl in gl_accounts
    ...     for l in gl.lines]

    >>> general_ledger = Report('account.general_ledger', context={
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     })
    >>> _ = general_ledger.execute(gl_accounts)

    >>> trial_balance = Report('account.trial_balance', context={
    ...     'company': company.id,
    ...     'fiscalyear': fiscalyear.id,
    ...     })
    >>> _ = trial_balance.execute(gl_accounts)

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

    >>> print_general_journal = Wizard('account.move.print_general_journal')
    >>> print_general_journal.execute('print_')
