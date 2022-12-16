====================
Move Cancel Scenario
====================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> today = datetime.date.today()

Install account::

    >>> config = activate_modules('account')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> party = Party(name='Party')
    >>> party.save()

Create Move to cancel::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(32)
    >>> line.party = customer
    >>> line.second_currency = get_currency('EUR')
    >>> line.amount_second_currency = Decimal(30)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(10)
    >>> line.party = party
    >>> move.save()
    >>> revenue.reload()
    >>> revenue.credit
    Decimal('42.00')
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('42.00')

Cancel Move::

    >>> cancel_move = Wizard('account.move.cancel', [move])
    >>> cancel_move.form.description = 'Cancel'
    >>> cancel_move.execute('cancel')
    >>> cancel_move.state
    'end'
    >>> move.reload()
    >>> [bool(l.reconciliation) for l in move.lines if l.account == receivable]
    [True, True]
    >>> line, _ = [l for l in move.lines if l.account == receivable]
    >>> cancel_move, = [l.move for l in line.reconciliation.lines
    ...     if l.move != move]
    >>> cancel_move.origin == move
    True
    >>> cancel_move.description
    'Cancel'
    >>> revenue.reload()
    >>> revenue.credit
    Decimal('0.00')
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('0.00')
