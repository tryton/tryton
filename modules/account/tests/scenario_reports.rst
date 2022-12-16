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

    >>> Module = Model.get('ir.module.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'account'),
    ...         ])
    >>> module.click('install')
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

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

    >>> print_general_ledger = Wizard('account.print_general_ledger')
    >>> print_general_ledger.form.start_period = None
    >>> print_general_ledger.form.end_period = None
    >>> print_general_ledger.execute('print_')

    >>> print_trial_balance = Wizard('account.print_trial_balance')
    >>> print_trial_balance.form.start_period = None
    >>> print_trial_balance.form.end_period = None
    >>> print_trial_balance.execute('print_')

    >>> third_party_balance = Wizard('account.open_third_party_balance')
    >>> third_party_balance.execute('print_')

    >>> aged_balance = Wizard('account.open_aged_balance')
    >>> aged_balance.execute('print_')

    >>> print_general_journal = Wizard('account.move.print_general_journal')
    >>> print_general_journal.execute('print_')
