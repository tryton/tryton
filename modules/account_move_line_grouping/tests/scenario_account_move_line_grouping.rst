===================================
Account Move Line Grouping Scenario
===================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond import backend
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'account_move_line_grouping', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Line = Model.get('account.move.line')
    >>> LineGroup = Model.get('account.move.line.group')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', "REV"),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', "CASH"),
    ...         ])

Create parties::

    >>> party = Party(name="Party")
    >>> party.save()

Create moves and reconciliation::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('20.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('22.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal('20.00')
    >>> line.party = party
    >>> line.maturity_date = period.end_date
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal('22.00')
    >>> line.party = party
    >>> line.maturity_date = period.end_date
    >>> move.save()

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.credit = Decimal('22.00')
    >>> line.party = party
    >>> line = move.lines.new()
    >>> line.account = accounts['cash']
    >>> line.debit = Decimal('22.00')
    >>> move.save()

    >>> lines = Line.find([
    ...         ('account', '=', accounts['receivable'].id),
    ...         ['OR',
    ...             ('debit', '=', Decimal(22)),
    ...             ('credit', '=', Decimal(22)),
    ...             ],
    ...         ])
    >>> reconcile_lines = Wizard('account.move.reconcile_lines', lines)

Check lines grouped::

    >>> lines = LineGroup.find([])
    >>> len(lines)
    4
    >>> line, = LineGroup.find([
    ...         ('account', '=', accounts['receivable'].id),
    ...         ('debit', '=', Decimal('42')),
    ...         ])
    >>> line.amount_reconciled
    Decimal('22.00')
    >>> if backend.name != 'sqlite':
    ...     line.partially_reconciled
    ... else:
    ...     True
    True
    >>> line.delegated_amount
    Decimal('0.00')
    >>> if backend.name != 'sqlite':
    ...     len(line.lines)
    ... else:
    ...     2
    2
    >>> line.payable_receivable_balance
    Decimal('42.00')

    >>> with config.set_context(reconciled=False):
    ...     line = LineGroup(line.id)
    >>> line.payable_receivable_balance
    Decimal('20.00')

    >>> line, = LineGroup.find([
    ...         ('account', '=', accounts['receivable'].id),
    ...         ('credit', '=', Decimal('22')),
    ...         ])
    >>> bool(line.reconciled)
    True
    >>> if backend.name != 'sqlite':
    ...     len(line.lines)
    ... else:
    ...     1
    1
