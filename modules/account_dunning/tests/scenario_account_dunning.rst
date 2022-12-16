========================
Account Dunning Scenario
========================

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
    ...         ('name', '=', 'account_dunning'),
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
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol='$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point='.')
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
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create account admin user::

    >>> account_admin_user = User()
    >>> account_admin_user.name = 'Account Admin'
    >>> account_admin_user.login = 'account_admin'
    >>> account_admin_group, = Group.find([
    ...         ('name', '=', 'Account Administration'),
    ...         ])
    >>> account_admin_user.groups.append(account_admin_group)
    >>> account_admin_user.save()

Create account user::

    >>> account_user = User()
    >>> account_user.name = 'Account'
    >>> account_user.login = 'account'
    >>> account_group, = Group.find([
    ...         ('name', '=', 'Account'),
    ...         ])
    >>> account_user.groups.append(account_group)
    >>> account_user.save()

Create dunning user::

    >>> dunning_user = User()
    >>> dunning_user.name = 'Dunning'
    >>> dunning_user.login = 'dunning'
    >>> dunning_group, = Group.find([('name', '=', 'Dunning')])
    >>> dunning_user.groups.append(dunning_group)
    >>> dunning_user.save()

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
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
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

Create dunning procedure::

    >>> config.user = account_admin_user.id
    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name='Procedure')
    >>> level = procedure.levels.new()
    >>> level.sequence = 1
    >>> level.days = 5
    >>> level = procedure.levels.new()
    >>> level.sequence = 2
    >>> level.days = 20
    >>> level = procedure.levels.new()
    >>> level.sequence = 3
    >>> level.days = 40
    >>> procedure.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.dunning_procedure = procedure
    >>> customer.save()

Create some moves::

    >>> config.user = account_user.id
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
    >>> line.credit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(100)
    >>> line.party = customer
    >>> line.maturity_date = period.start_date
    >>> move.save()
    >>> reconcile1, = [l for l in move.lines if l.account == receivable]
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(100)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]
    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(100)
    >>> line.party = customer
    >>> line.maturity_date = period.start_date
    >>> move.save()
    >>> dunning_line, = [l for l in move.lines if l.account == receivable]

Create dunnings on 4 days::

    >>> config.user = dunning_user.id
    >>> Dunning = Model.get('account.dunning')
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=4)
    >>> create_dunning.execute('create_')
    >>> Dunning.find([])
    []

Create dunnings on 5 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=5)
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])
    >>> dunning.procedure == procedure
    True
    >>> dunning.level == procedure.levels[0]
    True
    >>> dunning.state
    u'draft'
    >>> dunning.line == dunning_line
    True

Create dunnings on 30 days with draft dunning::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=30)
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])
    >>> dunning.procedure == procedure
    True
    >>> dunning.level == procedure.levels[0]
    True
    >>> dunning.state
    u'draft'
    >>> dunning.line == dunning_line
    True

Process dunning::

    >>> process_dunning = Wizard('account.dunning.process',
    ...     [dunning])
    >>> process_dunning.execute('process')
    >>> dunning.reload()
    >>> dunning.state
    u'done'

Create dunnings on 30 days with blocked dunning::

    >>> dunning.blocked = True
    >>> dunning.save()
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=30)
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])
    >>> dunning.procedure == procedure
    True
    >>> dunning.level == procedure.levels[0]
    True
    >>> dunning.state
    u'done'
    >>> dunning.line == dunning_line
    True
    >>> bool(dunning.blocked)
    True
    >>> dunning.blocked = False
    >>> dunning.save()

Create dunnings on 30 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=30)
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])
    >>> dunning.procedure == procedure
    True
    >>> dunning.level == procedure.levels[1]
    True
    >>> dunning.state
    u'draft'
    >>> dunning.line == dunning_line
    True

Pay dunning::

    >>> config.user = account_user.id
    >>> MoveLine = Model.get('account.move.line')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(100)
    >>> line.party = customer
    >>> move.save()
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]
    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [MoveLine(dunning.line.id), reconcile2])
    >>> Dunning.find([])
    []

Create dunnings on 50 days::

    >>> config.user = dunning_user.id
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=50)
    >>> create_dunning.execute('create_')
    >>> Dunning.find([])
    []
