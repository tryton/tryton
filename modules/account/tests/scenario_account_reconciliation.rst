===============================
Account Reconciliation Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
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
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create Moves for direct reconciliation::

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
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile1, = [l for l in move.lines if l.account == receivable]
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(42)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]

Reconcile Lines without writeoff::

    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> reconcile_lines.state == 'end'
    True
    >>> reconcile1.reload()
    >>> reconcile2.reload()
    >>> reconcile1.reconciliation == reconcile2.reconciliation != None
    True
    >>> len(reconcile1.reconciliation.lines)
    2

Create Moves for writeoff reconciliation::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(68)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(68)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile1, = [l for l in move.lines if l.account == receivable]
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(65)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(65)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]

Reconcile Lines with writeoff::

    >>> Sequence = Model.get('ir.sequence')
    >>> sequence_journal, = Sequence.find([('code', '=', 'account.journal')])
    >>> journal_writeoff = Journal(name='Write-Off', type='write-off',
    ...     sequence=sequence_journal,
    ...     credit_account=revenue, debit_account=expense)
    >>> journal_writeoff.save()
    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> reconcile_lines.form_state == 'writeoff'
    True
    >>> reconcile_lines.form.journal = journal_writeoff
    >>> reconcile_lines.execute('reconcile')
    >>> reconcile1.reload()
    >>> reconcile2.reload()
    >>> reconcile1.reconciliation == reconcile2.reconciliation != None
    True
    >>> len(reconcile1.reconciliation.lines)
    3
    >>> writeoff_line1, = [l for l in reconcile1.reconciliation.lines
    ...     if l.credit == Decimal(3)]
    >>> writeoff_line2, = [l for l in writeoff_line1.move.lines
    ...     if l != writeoff_line1]
    >>> writeoff_line2.account == expense
    True
    >>> writeoff_line2.debit
    Decimal('3.00')
