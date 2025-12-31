================================
Account Payment Overpay Scenario
================================

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

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create payable line::

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

Make partial payment::

    >>> payment_move = Move()
    >>> payment_move.journal = cash_journal
    >>> _ = payment_move.lines.new(
    ...     account=accounts['payable'], party=supplier,
    ...     debit=Decimal('50.00'))
    >>> _ = payment_move.lines.new(
    ...     account=accounts['cash'],
    ...     credit=Decimal('50.00'))
    >>> payment_move.click('post')
    >>> payment_move.state
    'posted'

Try to overpay the line::

    >>> line, = [l for l in move.lines if l.account == accounts['payable']]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    Traceback (most recent call last):
        ...
    OverpayWarning: ...

Make full payment::

    >>> payment_move2 = Move()
    >>> payment_move2.journal = cash_journal
    >>> _ = payment_move2.lines.new(
    ...     account=accounts['payable'], party=supplier,
    ...     debit=Decimal('50.00'))
    >>> _ = payment_move2.lines.new(
    ...     account=accounts['cash'],
    ...     credit=Decimal('50.00'))
    >>> payment_move2.click('post')
    >>> payment_move2.state
    'posted'

Try to overpay the line::

    >>> line, = [l for l in move.lines if l.account == accounts['payable']]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    Traceback (most recent call last):
        ...
    OverpayWarning: ...
