==================================
Negative Payment Clearing Scenario
==================================

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

    >>> config = activate_modules(
    ...     'account_payment_clearing', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']
    >>> expense = accounts['expense']

    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(parent=payable.parent)
    >>> bank_clearing.name = 'Bank Clearing'
    >>> bank_clearing.type = payable.type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
    >>> bank_clearing.save()

    >>> Journal = Model.get('account.journal')
    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual', clearing_journal=expense_journal,
    ...     clearing_account=bank_clearing)
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create payable move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = expense_journal
    >>> line = move.lines.new(
    ...     account=payable, party=supplier, maturity_date=today,
    ...     debit=Decimal('-50.00'))
    >>> line = move.lines.new(account=expense, credit=Decimal('-50.00'))
    >>> move.click('post')
    >>> payable.reload()
    >>> payable.balance
    Decimal('-50.00')

Pay the line::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('50.00')
    >>> payment.click('submit')
    >>> payment.click('approve')
    >>> payment.state
    'approved'
    >>> process_payment = payment.click('process_wizard')
    >>> payment.state
    'processing'

Succeed payment::

    >>> succeed = payment.click('succeed_wizard')
    >>> succeed.execute('succeed')
    >>> payment.state
    'succeeded'
    >>> payment.clearing_move.state
    'draft'
    >>> payable.reload()
    >>> payable.balance
    Decimal('0.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('-50.00')
    >>> bool(payment.line.reconciliation)
    True
