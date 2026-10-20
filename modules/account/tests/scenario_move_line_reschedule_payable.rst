=================================
Reschedule Payable Lines Scenario
=================================

Imports::

    >>> from decimal import Decimal

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Line = Model.get('account.move.line')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> party = Party(name="Party")
    >>> party.save()

Create Lines to reschedule::

    >>> journal_expense, = Journal.find([
    ...         ('code', '=', 'EXP'),
    ...         ])

    >>> move = Move()
    >>> move.journal = journal_expense
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['expense']
    >>> line.debit = Decimal('100.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['payable']
    >>> line.party = party
    >>> line.credit = Decimal('100.00')
    >>> line.maturity_date = period.start_date
    >>> move.save()

    >>> line, = [l for l in move.lines if l.account == accounts['payable']]
    >>> accounts['payable'].reload()
    >>> accounts['payable'].balance
    Decimal('-100.00')

Split line by amount::

    >>> reschedule = Wizard('account.move.line.reschedule', [line])
    >>> reschedule.form.total_amount
    Decimal('-100.00')
    >>> reschedule.form.start_date = period.end_date
    >>> reschedule.form.frequency = 'other'
    >>> reschedule.form.interval = 2
    >>> reschedule.form.amount = Decimal('-30.00')
    >>> reschedule.execute('preview')

    >>> term1, term2, term3, term4 = reschedule.form.terms
    >>> assertEqual(term1.date, period.end_date)
    >>> assertEqual(term2.date, period.end_date + relativedelta(months=2))
    >>> assertEqual(term3.date, period.end_date + relativedelta(months=4))
    >>> assertEqual(term4.date, period.end_date + relativedelta(months=6))
    >>> term1.amount, term2.amount, term3.amount, term4.amount
    (Decimal('-30.00'), Decimal('-30.00'), Decimal('-30.00'), Decimal('-10.00'))

    >>> reschedule.execute('reschedule')

Check payable::

    >>> accounts['payable'].reload()
    >>> accounts['payable'].balance
    Decimal('-100.00')

    >>> lines = Line.find([
    ...     ('account', '=', accounts['payable'].id),
    ...     ('reconciliation', '=', None),
    ...     ], order=[('maturity_date', 'ASC')])
    >>> [l.amount for l in lines]
    [Decimal('-30.00'), Decimal('-30.00'), Decimal('-30.00'), Decimal('-10.00')]
