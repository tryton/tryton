================
Payment Scenario
================

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

Activate modules::

    >>> config = activate_modules('account_payment', create_company, create_chart)

Set employee::

    >>> User = Model.get('res.user')
    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> user = User(config.user)
    >>> user.employees.append(employee)
    >>> user.employee = employee
    >>> user.save()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(today=(today, tomorrow))
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

    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create payable move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = expense_journal
    >>> line = move.lines.new(
    ...     account=payable, party=supplier, maturity_date=tomorrow,
    ...     credit=Decimal('50.00'))
    >>> line = move.lines.new(account=expense, debit=Decimal('50.00'))
    >>> move.click('post')

Partially pay line::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.date = tomorrow
    >>> pay_line.execute('next_')
    >>> assertEqual(pay_line.form.journal, payment_journal)
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()
    >>> bool(payment.number)
    True
    >>> assertEqual(payment.date, tomorrow)
    >>> assertEqual(payment.party, supplier)
    >>> payment.amount
    Decimal('50.00')
    >>> payment.amount = Decimal('20.00')
    >>> payment.click('submit')
    >>> assertEqual(payment.submitted_by, employee)
    >>> payment.click('approve')
    >>> assertEqual(payment.approved_by, employee)
    >>> payment.state
    'approved'
    >>> process_payment = payment.click('process_wizard')
    >>> group, = process_payment.actions[0]
    >>> assertEqual(group.payments, [payment])
    >>> payment.state
    'processing'
    >>> line.reload()
    >>> line.payment_amount
    Decimal('30.00')

Check the properties of the payment group::

    >>> group = payment.group
    >>> group.payment_count
    1
    >>> group.payment_amount
    Decimal('20.00')
    >>> group.payment_amount_succeeded
    >>> group.payment_complete
    False

Success the payment and recheck the payment group::

    >>> group.click('succeed')
    >>> payment.reload()
    >>> assertEqual(payment.succeeded_by, employee)
    >>> payment.state
    'succeeded'
    >>> group.reload()
    >>> group.payment_amount_succeeded
    Decimal('20.00')
    >>> group.payment_complete
    True

Search for the completed payment::

    >>> PaymentGroup = Model.get('account.payment.group')
    >>> group, = PaymentGroup.find([('payment_complete', '=', 'True')])
    >>> group.payment_complete
    True
    >>> assertEqual(group, payment.group)

Partially fail to pay the remaining::

    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('30.00')
    >>> payment.click('submit')
    >>> payment.click('approve')
    >>> process_payment = payment.click('process_wizard')
    >>> line.reload()
    >>> line.payment_amount
    Decimal('0.00')
    >>> payment.reload()
    >>> payment.click('fail')
    >>> assertEqual(payment.failed_by, employee)
    >>> payment.state
    'failed'
    >>> payment.group.payment_complete
    True
    >>> payment.group.payment_amount_succeeded
    >>> line.reload()
    >>> line.payment_amount
    Decimal('30.00')

Pay line and block it after::

    >>> move, = move.duplicate()
    >>> move.click('post')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> len(line.payments)
    1

    >>> line.click('payment_block')
    >>> len(line.payments)
    0

Try to pay blocked line::

    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    Traceback (most recent call last):
        ...
    BlockedWarning: ...
