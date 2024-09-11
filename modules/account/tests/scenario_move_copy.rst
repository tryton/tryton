==================
Move Copy Scenario
==================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import (
    ...     activate_modules, assertEqual, assertNotEqual, assertTrue)

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Create a fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

Create a party::

    >>> party = Party(name="Party")
    >>> party.save()

Create a posted move::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal, = Journal.find([('code', '=', 'REV')])
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(42)
    >>> line.party = party
    >>> move.save()
    >>> move.click('post')
    >>> move.state
    'posted'

Copy move on open period::

    >>> copy_move, = move.duplicate()
    >>> assertTrue(copy_move.number)
    >>> copy_move.post_number
    >>> copy_move.state
    'draft'
    >>> copy_move.post_date
    >>> assertEqual(copy_move.period, move.period)
    >>> assertEqual(copy_move.date, move.date)
    >>> copy_move.delete()

Copy move on closed period::

    >>> period.click('close')
    >>> period.state
    'closed'

    >>> copy_move, = move.duplicate()
    Traceback (most recent call last):
        ...
    CopyWarning: ...

    >>> config.skip_warning = True
    >>> copy_move, = move.duplicate()
    >>> assertTrue(copy_move.number)
    >>> copy_move.post_number
    >>> copy_move.state
    'draft'
    >>> copy_move.post_date
    >>> assertNotEqual(copy_move.period, move.period)
    >>> copy_move.period.state
    'open'
    >>> assertNotEqual(copy_move.date, move.date)
