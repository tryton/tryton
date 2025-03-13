===================================
Account Move Line Grouping Scenario
===================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond import backend
    >>> from trytond.tests.tools import activate_modules

    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('account_move_line_grouping')

    >>> Journal = Model.get('account.journal')
    >>> Line = Model.get('account.move.line')
    >>> LineGroup = Model.get('account.move.line.group')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

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
    >>> line.credit = Decimal(20)
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(22)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(20)
    >>> line.party = party
    >>> line.maturity_date = period.end_date
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(22)
    >>> line.party = party
    >>> line.maturity_date = period.end_date
    >>> move.save()

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.credit = Decimal(22)
    >>> line.party = party
    >>> line = move.lines.new()
    >>> line.account = accounts['cash']
    >>> line.debit = Decimal(22)
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
    >>> line.amount_reconciled == Decimal(22)
    True
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
    >>> line.payable_receivable_balance == Decimal('42.00')
    True

    >>> with config.set_context(reconciled=False):
    ...     line = LineGroup(line.id)
    >>> line.payable_receivable_balance == Decimal('20.00')
    True

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
