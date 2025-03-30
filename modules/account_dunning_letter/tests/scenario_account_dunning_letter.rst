========================
Account Dunning Scenario
========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'account_dunning_letter', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> cash = accounts['cash']

Create dunning procedure::

    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name='Procedure')
    >>> level = procedure.levels.new()
    >>> level.sequence = 1
    >>> level.overdue = dt.timedelta(5)
    >>> level.print_on_letter = True
    >>> procedure.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.dunning_procedure = procedure
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

Create reconciled moves::

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
    >>> create_dunning.form.date = period.start_date + dt.timedelta(days=5)
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])

Process dunning::

    >>> process_dunning = Wizard('account.dunning.process',
    ...     [dunning])
    >>> process_dunning.execute('process')
    >>> dunning.reload()
    >>> dunning.state
    'waiting'
    >>> (_, _, _, _), = process_dunning.actions
