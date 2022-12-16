==============================
Account Dunning Email Scenario
==============================

Imports::

    >>> import datetime
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Activate modules::

    >>> config = activate_modules('account_dunning_email')

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
    >>> cash = accounts['cash']

Create dunning procedure::

    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name="Procedure")
    >>> level = procedure.levels.new()
    >>> level.sequence = 1
    >>> level.overdue = datetime.timedelta(5)
    >>> level.send_email = True
    >>> level.email_from = 'noreply@example.com'
    >>> procedure.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.dunning_procedure = procedure
    >>> email = customer.contact_mechanisms.new(type='email')
    >>> email.value = 'customer@example.com'
    >>> customer.save()

Create some moves::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

Create due move of 100::

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

Add partial payment of 50::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(50)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(50)
    >>> line.party = customer
    >>> move.save()

Create dunnings::

    >>> Dunning = Model.get('account.dunning')
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = period.start_date + datetime.timedelta(days=5)
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])

Process dunning::

    >>> process_dunning = Wizard('account.dunning.process',
    ...     [dunning])
    >>> process_dunning.execute('process')
    >>> dunning.reload()
    >>> dunning.state
    'waiting'
