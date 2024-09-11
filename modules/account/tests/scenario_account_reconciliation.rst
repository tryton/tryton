===============================
Account Reconciliation Scenario
===============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertTrue

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> GLLine = Model.get('account.general_ledger.line')

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
    >>> reconcile_lines.state
    'end'
    >>> reconcile1.reload()
    >>> reconcile2.reload()
    >>> assertEqual(reconcile1.reconciliation, reconcile2.reconciliation)
    >>> assertTrue(reconcile1.reconciliation)
    >>> len(reconcile1.reconciliation.lines)
    2

Unreconcile lines::

    >>> unreconcile_lines = Wizard(
    ...     'account.move.unreconcile_lines', [reconcile1])
    >>> unreconcile_lines.state
    'end'
    >>> reconcile1.reload()
    >>> reconcile1.reconciliation
    >>> reconcile2.reload()
    >>> reconcile2.reconciliation

Reconcile general ledger lines::

    >>> gl_reconcile1 = GLLine(reconcile1.id)
    >>> gl_reconcile2 = GLLine(reconcile2.id)
    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [gl_reconcile1, gl_reconcile2])
    >>> reconcile_lines.state
    'end'
    >>> gl_reconcile1.reload()
    >>> gl_reconcile2.reload()
    >>> assertEqual(gl_reconcile1.reconciliation, gl_reconcile2.reconciliation)
    >>> assertTrue(gl_reconcile1.reconciliation)

Unreconcile general ledger, lines::

    >>> unreconcile_lines = Wizard(
    ...     'account.move.unreconcile_lines', [gl_reconcile1])
    >>> unreconcile_lines.state
    'end'
    >>> gl_reconcile1.reload()
    >>> gl_reconcile1.reconciliation
    >>> gl_reconcile2.reload()
    >>> gl_reconcile2.reconciliation

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

Create a write-off payment method::

    >>> Sequence = Model.get('ir.sequence')
    >>> sequence_journal, = Sequence.find(
    ...     [('sequence_type.name', '=', "Account Journal")], limit=1)
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

Reconcile Lines with write-off::

    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> reconcile_lines.form_state
    'writeoff'
    >>> reconcile_lines.form.writeoff = writeoff_method
    >>> reconcile_lines.execute('reconcile')
    >>> reconcile1.reload()
    >>> reconcile2.reload()
    >>> assertEqual(reconcile1.reconciliation, reconcile2.reconciliation)
    >>> assertTrue(reconcile1.reconciliation)
    >>> len(reconcile1.reconciliation.lines)
    3
    >>> writeoff_line1, = [l for l in reconcile1.reconciliation.lines
    ...     if l.credit == Decimal(3)]
    >>> writeoff_line2, = [l for l in writeoff_line1.move.lines
    ...     if l != writeoff_line1]
    >>> assertEqual(writeoff_line2.account, expense)
    >>> writeoff_line2.debit
    Decimal('3')
