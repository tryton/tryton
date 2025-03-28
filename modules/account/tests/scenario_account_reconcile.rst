==========================
Account Reconcile Scenario
==========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> party_required = globals().get('party_required', True)

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Line = Model.get('account.move.line')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

    >>> receivable.party_required = party_required
    >>> receivable.save()

Create parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create Moves to reconcile::

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
    >>> if line.account.party_required:
    ...     line.party = customer
    >>> move.save()

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(40)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(40)
    >>> if line.account.party_required:
    ...     line.party = customer
    >>> move.save()

Create a write off method::

    >>> journal_writeoff = Journal(name='Write-Off', type='write-off')
    >>> journal_writeoff.save()
    >>> WriteOff = Model.get('account.move.reconcile.write_off')
    >>> writeoff_method = WriteOff()
    >>> writeoff_method.name = 'Write Off'
    >>> writeoff_method.journal = journal_writeoff
    >>> writeoff_method.debit_account = expense
    >>> writeoff_method.credit_account = expense
    >>> writeoff_method.save()

Run Reconcile for only balanced::

    >>> reconcile = Wizard('account.reconcile')
    >>> reconcile.form.only_balanced = True
    >>> reconcile.execute('setup')
    >>> reconcile.state
    'end'

Run Reconcile wizard::

    >>> reconcile = Wizard('account.reconcile')
    >>> reconcile.execute('setup')
    >>> assertEqual(reconcile.form.party, (customer if party_required else None))
    >>> reconcile.form.write_off_amount
    Decimal('0.00')
    >>> len(reconcile.form.lines)
    0
    >>> reconcile.form.lines.extend(reconcile.form.lines.find())
    >>> len(reconcile.form.lines)
    2
    >>> reconcile.form.write_off_amount
    Decimal('2.00')
    >>> reconcile.form.write_off = writeoff_method
    >>> reconcile.execute('reconcile')

    >>> lines = Line.find([('account', '=', receivable.id)])
    >>> len(lines)
    3
    >>> all(l.reconciliation for l in lines)
    True
