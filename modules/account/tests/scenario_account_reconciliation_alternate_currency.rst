=========================================
Account Reconciliation Alternate Currency
=========================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('account')

    >>> Configuration = Model.get('account.configuration')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> Reconciliation = Model.get('account.move.reconciliation')

Create currencies::

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')

Create company::

    >>> _ = create_company(currency=usd)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Configure currency exchange::

    >>> currency_exchange_account, = (
    ...     accounts['revenue'].duplicate(
    ...         default={'name': "Currency Exchange"}))
    >>> configuration = Configuration(1)
    >>> configuration.currency_exchange_credit_account = (
    ...     currency_exchange_account)
    >>> configuration.save()

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Create moves to reconcile::

    >>> journal_expense, = Journal.find([('code', '=', 'EXP')])
    >>> journal_cash, = Journal.find([('code', '=', 'CASH')])

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_expense
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['expense']
    >>> line.debit = Decimal('50.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['payable']
    >>> line.party = party
    >>> line.credit = Decimal('50.00')
    >>> line.amount_second_currency = Decimal('-90.00')
    >>> line.second_currency = eur
    >>> move.save()
    >>> reconcile1, = [l for l in move.lines if l.account == accounts['payable']]

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.end_date
    >>> line = move.lines.new()
    >>> line.account = accounts['cash']
    >>> line.credit = Decimal('45.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['payable']
    >>> line.party = party
    >>> line.debit = Decimal('45.00')
    >>> line.amount_second_currency = Decimal('-90.00')
    >>> line.second_currency = eur
    >>> move.save()
    >>> reconcile2, = [l for l in move.lines if l.account == accounts['payable']]

Reconcile lines::

    >>> reconcile_lines = Wizard(
    ...     'account.move.reconcile_lines', [reconcile1, reconcile2])
    >>> reconcile_lines.state
    'end'

    >>> reconcile1.reconciliation == reconcile2.reconciliation != None
    True
    >>> reconciliation, = Reconciliation.find([])
    >>> len(reconciliation.lines)
    3
    >>> currency_exchange_account.reload()
    >>> currency_exchange_account.balance
    Decimal('-5.00')
