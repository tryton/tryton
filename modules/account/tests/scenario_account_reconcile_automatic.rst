====================================
Account Reconcile Automatic Scenario
====================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('account')

    >>> Journal = Model.get('account.journal')
    >>> Line = Model.get('account.move.line')
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

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create Moves to reconcile::

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
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.save()

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['cash']
    >>> line.debit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.credit = Decimal(42)
    >>> line.party = customer
    >>> move.save()

Run Reconcile wizard::

    >>> reconcile = Wizard('account.reconcile')
    >>> reconcile.form.automatic = True
    >>> reconcile.execute('next_')

    >>> lines = Line.find([('account', '=', accounts['receivable'].id)])
    >>> len(lines)
    2
    >>> all(l.reconciliation for l in lines)
    True
