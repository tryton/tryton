========================================================
Account Reconciliation Alternate Currency with Write-Off
========================================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)

    >>> post_moves = globals().get('post_moves', False)

Activate modules::

    >>> config = activate_modules('account')

    >>> Configuration = Model.get('account.configuration')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> Reconciliation = Model.get('account.move.reconciliation')
    >>> WriteOff = Model.get('account.move.reconcile.write_off')

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

Create write-off::

    >>> journal_writeoff = Journal(
    ...     name="Write-Off", type='write-off')
    >>> journal_writeoff.save()
    >>> write_off = WriteOff()
    >>> write_off.name = "Write-Off"
    >>> write_off.journal = journal_writeoff
    >>> write_off.debit_account, = accounts['expense'].duplicate()
    >>> write_off.credit_account, = accounts['revenue'].duplicate()
    >>> write_off.save()

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
    >>> if post_moves:
    ...     move.click('post')
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
    >>> line.amount_second_currency = Decimal('-89.00')
    >>> line.second_currency = eur
    >>> move.save()
    >>> if post_moves:
    ...     move.click('post')
    >>> reconcile2, = [l for l in move.lines if l.account == accounts['payable']]

Reconcile lines::

    >>> reconcile_lines = Wizard(
    ...     'account.move.reconcile_lines', [reconcile1, reconcile2])
    >>> reconcile_lines.form_state
    'writeoff'
    >>> reconcile_lines.form.writeoff = write_off
    >>> reconcile_lines.execute('reconcile')

    >>> reconcile1.reconciliation == reconcile2.reconciliation != None
    True
    >>> reconciliation, = Reconciliation.find([])
    >>> len(reconciliation.lines)
    4
    >>> write_off.credit_account.reload()
    >>> write_off.credit_account.balance
    Decimal('-0.50')
    >>> currency_exchange_account.reload()
    >>> currency_exchange_account.balance
    Decimal('-4.50')

    >>> len(Move.find([('state', '=', 'posted' if post_moves else 'draft')]))
    4
