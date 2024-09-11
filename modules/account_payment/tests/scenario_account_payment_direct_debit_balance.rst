=============================================
Account Payment Direct Debit Balance Scenario
=============================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertIsNone

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

    >>> revnue_journal, = Journal.find([('code', '=', 'REV')])

Create payment journal::

    >>> payment_journal = PaymentJournal(
    ...     name="Manual", process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> _ = customer.reception_direct_debits.new(
    ...     journal=payment_journal, type='balance')
    >>> customer.save()

Create receivable moves::

    >>> move = Move()
    >>> move.journal = revnue_journal
    >>> line = move.lines.new(
    ...     account=accounts['receivable'], party=customer,
    ...     debit=Decimal('100.00'), maturity_date=today)
    >>> line = move.lines.new(
    ...     account=accounts['revenue'],
    ...     credit=Decimal('100.00'))
    >>> move.click('post')

Create direct debit::

    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.execute('create_')

    >>> payment, = Payment.find([])
    >>> payment.amount
    Decimal('100.00')
    >>> assertEqual(payment.party, customer)
    >>> assertEqual(payment.journal, payment_journal)
    >>> assertIsNone(payment.line)
    >>> payment.amount = Decimal('25.00')
    >>> payment.save()

Re-run create a second direct debit::

    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.execute('create_')

    >>> payment2, = Payment.find([('id', '!=', payment.id)])
    >>> payment2.amount
    Decimal('75.00')

Re-run create direct debit does nothing::

    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.execute('create_')

    >>> assertEqual(Payment.find([]), [payment, payment2])
