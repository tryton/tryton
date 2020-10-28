=========================
Payment Planning Scenario
=========================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> today = datetime.date.today()
    >>> tomorrow = today + datetime.timedelta(days=1)
    >>> next_week = today + datetime.timedelta(weeks=1)

Activate modules::

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
    >>> payment.date == next_week
    True

The date on the payment wizard is used for payment date::

    >>> payment.delete()
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.date = tomorrow
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()
    >>> payment.date == tomorrow
    True

If the line does not have any maturity date it is scheduled for today::

    >>> payment.delete()
    >>> line.maturity_date = None
    >>> line.save()
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = line.payments
    >>> payment.date == today
    True
