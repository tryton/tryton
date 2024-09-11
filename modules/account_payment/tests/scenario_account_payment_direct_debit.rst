=============================
Payment Direct Debit Scenario
=============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertIsNotNone

    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(days=1)
    >>> after_tomorrow = tomorrow + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('account_payment', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> Payment = Model.get('account.payment')
    >>> PaymentJournal = Model.get('account.payment.journal')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(today=(today, after_tomorrow))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

    >>> revnue_journal, = Journal.find([('code', '=', 'REV')])

Create payment journal::

    >>> payment_journal = PaymentJournal(
    ...     name="Manual", process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> customer1 = Party(name="Customer 1")
    >>> _ = customer1.reception_direct_debits.new(journal=payment_journal)
    >>> customer1.save()
    >>> customer2 = Party(name="Customer 2")
    >>> customer2.save()

Create receivable moves::

    >>> move = Move()
    >>> move.journal = revnue_journal
    >>> line = move.lines.new(
    ...     account=accounts['receivable'], party=customer1,
    ...     debit=Decimal('100.00'), maturity_date=tomorrow)
    >>> line = move.lines.new(
    ...     account=accounts['revenue'],
    ...     credit=Decimal('100.00'))
    >>> move.click('post')

    >>> move = Move()
    >>> move.journal = revnue_journal
    >>> line = move.lines.new(
    ...     account=accounts['receivable'], party=customer2,
    ...     debit=Decimal('200.00'), maturity_date=tomorrow)
    >>> line = move.lines.new(
    ...     account=accounts['revenue'],
    ...     credit=Decimal('200.00'))
    >>> move.click('post')

Create direct debit::

    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.form.date = after_tomorrow
    >>> create_direct_debit.execute('create_')

    >>> payment, = Payment.find([])
    >>> payment.amount
    Decimal('100.00')
    >>> assertEqual(payment.party, customer1)
    >>> assertEqual(payment.date, tomorrow)
    >>> assertEqual(payment.journal, payment_journal)
    >>> assertIsNotNone(payment.line)

Re-run create direct debit does nothing::

    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.form.date = after_tomorrow
    >>> create_direct_debit.execute('create_')

    >>> assertEqual(Payment.find([]), [payment])
