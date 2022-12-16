===============================
Account Reconciliation Scenario
===============================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', '=', 'account'),
    ...         ])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='B2CK')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name='%s' % today.year)
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_sequence = Sequence(name='%s' % today.year,
    ...     code='account.move', company=company)
    >>> post_move_sequence.save()
    >>> fiscalyear.post_move_sequence = post_move_sequence
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', False)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> cash, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'Main Cash'),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

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
    >>> line.party = customer
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
    >>> line.party = customer
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(65)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]

Reconcile Lines with writeoff::

    >>> journal_expense, = Journal.find([
    ...         ('code', '=', 'EXP'),
    ...         ])
    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> reconcile_lines.form_state == 'writeoff'
    True
    >>> reconcile_lines.form.journal = journal_expense
    >>> reconcile_lines.form.account = expense
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
    >>> writeoff_line2.debit == Decimal(3)
    True
