=================================
Account Payment Warnings Scenario
=================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_payment', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> Payment = Model.get('account.payment')
    >>> PaymentJournal = Model.get('account.payment.journal')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])
    >>> cash_journal, = Journal.find([('code', '=', 'CASH')])

Create payment journal::

    >>> payment_journal = PaymentJournal(
    ...     name="Manual", process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> supplier2 = Party(name="Supplier 2")
    >>> supplier2.save()

Create receivable moves::

    >>> move = Move()
    >>> move.journal = expense_journal
    >>> line = move.lines.new(
    ...     account=accounts['payable'], party=supplier, maturity_date=today,
    ...     credit=Decimal('100.00'))
    >>> line = move.lines.new(
    ...     account=accounts['expense'],
    ...     debit=Decimal('100.00'))
    >>> move.click('post')
    >>> move.state
    'posted'
    >>> move2, = move.duplicate()
    >>> move2.click('post')

Pay line::

    >>> line, = [l for l in move.lines if l.account == accounts['payable']]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.date = today
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()

Try to cancel move::

    >>> cancel_move = Wizard('account.move.cancel', [move])
    >>> cancel_move.execute('cancel')
    Traceback (most recent call last):
        ...
    CancelWarning: ...

Try to group lines::

    >>> line2, = [l for l in move2.lines if l.account == accounts['payable']]
    >>> group_line = Wizard('account.move.line.group', [line, line2])
    >>> group_line.execute('group')
    Traceback (most recent call last):
        ...
    GroupLineWarning: ...

Try to reschedule line::

    >>> reschedule_line = Wizard('account.move.line.reschedule', [line])
    >>> reschedule_line.form.start_date = today
    >>> reschedule_line.form.frequency = 'monthly'
    >>> reschedule_line.form.interval = 1
    >>> reschedule_line.form.amount = Decimal('50.00')
    >>> reschedule_line.execute('preview')
    >>> reschedule_line.execute('reschedule')
    Traceback (most recent call last):
        ...
    RescheduleLineWarning: ...

Try to delegate line::

    >>> delegate_line = Wizard('account.move.line.delegate', [line])
    >>> delegate_line.form.party = supplier2
    >>> delegate_line.execute('delegate')
    Traceback (most recent call last):
        ...
    DelegateLineWarning: ...

Reconcile line and try to submit::

    >>> move = Move()
    >>> move.journal = cash_journal
    >>> _ = move.lines.new(
    ...     account=accounts['payable'], party=supplier,
    ...     debit=Decimal('100.00'))
    >>> _ = move.lines.new(
    ...     account=accounts['cash'],
    ...     credit=Decimal('100.00'))
    >>> move.click('post')
    >>> move.state
    'posted'

    >>> cash_line, = [l for l in move.lines if l.account == accounts['payable']]
    >>> reconcile = Wizard('account.move.reconcile_lines', [payment.line, cash_line])
    >>> reconcile.state
    'end'

    >>> payment.click('submit')
    Traceback (most recent call last):
        ...
    ReconciledWarning: ...
