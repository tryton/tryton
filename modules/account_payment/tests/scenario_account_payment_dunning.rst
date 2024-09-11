================================
Account Payment Dunning Scenario
================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment', 'account_dunning'], create_company, create_chart)

    >>> Dunning = Model.get('account.dunning')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Procedure = Model.get('account.dunning.procedure')

Get accounts::

    >>> accounts = get_accounts()

    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(today=today)
    >>> fiscalyear.click('create_period')

Create dunning procedure::

    >>> procedure = Procedure(name='Procedure')
    >>> level = procedure.levels.new(overdue=dt.timedelta(0))
    >>> procedure.save()

Create payment journal::

    >>> payment_journal = PaymentJournal(
    ...     name='Manual',
    ...     process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> customer = Party(name='Customer')
    >>> customer.dunning_procedure = procedure
    >>> customer.save()

Create payable move::

    >>> move = Move()
    >>> move.journal = expense_journal
    >>> line = move.lines.new()
    >>> line.party = customer
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal('50.00')
    >>> line.maturity_date = today
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('50.00')
    >>> move.click('post')

Make a payment::

    >>> line, = [l for l in move.lines if l.account == accounts['receivable']]
    >>> line.payment_amount
    Decimal('50.00')
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = line.payments
    >>> line.payment_amount
    Decimal('0.00')

Create no dunning::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.execute('create_')
    >>> Dunning.find([])
    []

Fail the payment::

    >>> payment.click('submit')
    >>> process_payment = payment.click('process_wizard')
    >>> group, = process_payment.actions[0]
    >>> assertEqual(group.payments, [payment])
    >>> payment.click('fail')
    >>> payment.state
    'failed'
    >>> line.reload()
    >>> line.payment_amount
    Decimal('50.00')

Create dunning::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])
    >>> assertEqual(dunning.line, line)

Recreate a payment::

    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> _, payment = line.payments
    >>> payment.state
    'draft'

Dunning is inactive::

    >>> dunning.reload()
    >>> dunning.active
    False
    >>> Dunning.find([])
    []
