================
Payment Scenario
================

Imports::
    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install account_payment::

    >>> config = activate_modules('account_payment')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> payable = accounts['payable']

    >>> Journal = Model.get('account.journal')
    >>> expense, = Journal.find([('code', '=', 'EXP')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create payable move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = expense
    >>> line = move.lines.new(account=payable, party=supplier,
    ...     credit=Decimal('50.00'))
    >>> line = move.lines.new(account=expense, debit=Decimal('50.00'))
    >>> move.click('post')

Partially pay line::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal == payment_journal
    True
    >>> pay_line.execute('start')
    >>> payment, = Payment.find()
    >>> payment.party == supplier
    True
    >>> payment.amount
    Decimal('50.00')
    >>> payment.amount = Decimal('20.00')
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'
    >>> line.reload()
    >>> line.payment_amount
    Decimal('30.00')

Partially fail to pay the remaining::

    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('start')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('30.00')
    >>> payment.click('approve')
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> line.reload()
    >>> line.payment_amount
    Decimal('0.00')
    >>> payment.reload()
    >>> payment.click('fail')
    >>> payment.state
    u'failed'
    >>> line.reload()
    >>> line.payment_amount
    Decimal('30.00')

Pay line and block it after::

    >>> move, = move.duplicate()
    >>> move.click('post')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('start')
    >>> len(line.payments)
    1

    >>> line.click('payment_block')
    >>> len(line.payments)
    0

Try to pay blocked line::

    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('start')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserWarning: ...
