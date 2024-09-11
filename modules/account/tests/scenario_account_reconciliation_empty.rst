=====================================
Account Reconciliation Empty Scenario
=====================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertTrue

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')

Create currencies::

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> account = accounts['cash']
    >>> account.reconcile = True
    >>> account.save()
    >>> journal, = Journal.find([('code', '=', 'CASH')])

Lines with empty debit/credit are reconciled::

    >>> move = Move()
    >>> move.journal = journal
    >>> line = move.lines.new()
    >>> line.account = account
    >>> line.debit = line.credit = Decimal('0')
    >>> move.save()
    >>> move.click('post')
    >>> move.state
    'posted'
    >>> line, = move.lines
    >>> assertTrue(line.reconciliation)

Lines with empty debit/credit but second currency are not reconciled::

    >>> move = Move()
    >>> move.journal = journal
    >>> line = move.lines.new()
    >>> line.account = account
    >>> line.debit = line.credit = Decimal('0')
    >>> line.amount_second_currency = Decimal('0.15')
    >>> line.second_currency = eur
    >>> move.save()
    >>> move.click('post')
    >>> move.state
    'posted'
    >>> line, = move.lines
    >>> line.reconciliation
