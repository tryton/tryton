=====================================
Payment Blocked Direct Debit Scenario
=====================================

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
    >>> Line = Model.get('account.move.line')
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
    >>> _ = customer.reception_direct_debits.new(journal=payment_journal)
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

Direct debit is not created when payment blocked::

    >>> line, = Line.find([('party', '=', customer.id)])
    >>> line.click('payment_block')
    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.form.date = today
    >>> create_direct_debit.execute('create_')
    >>> len(Payment.find([]))
    0

Direct debit is created when payment is unblocked::

    >>> line.click('payment_unblock')
    >>> create_direct_debit = Wizard('account.move.line.create_direct_debit')
    >>> create_direct_debit.form.date = today
    >>> create_direct_debit.execute('create_')
    >>> len(Payment.find([]))
    1
