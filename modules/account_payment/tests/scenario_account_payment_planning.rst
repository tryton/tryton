=========================
Payment Planning Scenario
=========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(days=1)
    >>> next_week = today + dt.timedelta(weeks=1)

Activate modules::

    >>> config = activate_modules('account_payment', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(today=(today, next_week))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> payable = accounts['payable']
    >>> expense = accounts['expense']

    >>> Journal = Model.get('account.journal')
    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create payable move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = expense_journal
    >>> line = move.lines.new(account=payable, party=supplier,
    ...     credit=Decimal('50.00'), maturity_date=next_week)
    >>> line = move.lines.new(account=expense, debit=Decimal('50.00'))
    >>> move.click('post')

Paying the line without date uses the maturity date::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()
    >>> assertEqual(payment.date, next_week)

The date on the payment wizard is used for payment date::

    >>> payment.delete()
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.date = tomorrow
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()
    >>> assertEqual(payment.date, tomorrow)
