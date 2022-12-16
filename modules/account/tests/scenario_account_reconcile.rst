==========================
Account Reconcile Scenario
==========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install account::

    >>> config = activate_modules('account')

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

Create Moves to reconcile::

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
    >>> line.party = customer
    >>> move.save()

Create a write off method::

    >>> Sequence = Model.get('ir.sequence')
    >>> sequence_journal, = Sequence.find([('code', '=', 'account.journal')])
    >>> journal_writeoff = Journal(name='Write-Off', type='write-off',
    ...     sequence=sequence_journal)
    >>> journal_writeoff.save()
    >>> WriteOff = Model.get('account.move.reconcile.write_off')
    >>> writeoff_method = WriteOff()
    >>> writeoff_method.name = 'Write Off'
    >>> writeoff_method.journal = journal_writeoff
    >>> writeoff_method.debit_account = expense
    >>> writeoff_method.credit_account = expense
    >>> writeoff_method.save()

Run Reconcile wizard::

    >>> reconcile = Wizard('account.reconcile')
    >>> reconcile.form.party == customer
    True
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
