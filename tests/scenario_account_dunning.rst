========================
Account Dunning Scenario
========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> today = datetime.date.today()

Install account_dunning::

    >>> config = activate_modules('account_dunning')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create account admin user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
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

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> cash = accounts['cash']

Create dunning procedure::

    >>> set_user(account_admin_user)
    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name='Procedure')
    >>> level = procedure.levels.new()
    >>> level.sequence = 1
    >>> level.overdue = datetime.timedelta(5)
    >>> level = procedure.levels.new()
    >>> level.sequence = 2
    >>> level.overdue = datetime.timedelta(20)
    >>> level = procedure.levels.new()
    >>> level.sequence = 3
    >>> level.overdue = datetime.timedelta(40)
    >>> procedure.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.dunning_procedure = procedure
    >>> customer.save()

Create some moves::

    >>> set_user(account_user)
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

    >>> set_user(dunning_user)
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

    >>> set_user(account_user)
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

    >>> set_user(dunning_user)
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + relativedelta(days=50)
    >>> create_dunning.execute('create_')
    >>> Dunning.find([])
    []
