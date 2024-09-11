=======================
Account Export Scenario
=======================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('account_export', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> MoveExport = Model.get('account.move.export')
    >>> Party = Model.get('party.party')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Create a move::

    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ], limit=1)
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.party = party
    >>> line.debit = Decimal(42)
    >>> move.save()
    >>> move.click('post')
    >>> move.state
    'posted'

Create move export::

    >>> move_export = MoveExport()
    >>> move_export.save()
    >>> move_export.state
    'draft'
    >>> len(move_export.moves)
    0

Select moves for export::

    >>> move_export.click('select_moves')
    >>> len(move_export.moves)
    1

Try to delete move export done::

    >>> move_export.click('wait')
    >>> move_export.state
    'waiting'
    >>> move_export.click('wait')
    >>> move_export.click('do')
    >>> move_export.state
    'done'

    >>> move_export.delete()
    Traceback (most recent call last):
        ...
    AccessError: ...

Copy move export does not copy moves::

    >>> move_export, = move_export.duplicate()
    >>> len(move_export.moves)
    0
