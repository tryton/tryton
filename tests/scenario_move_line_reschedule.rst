=========================
Reschedule Lines Scenario
=========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
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

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=usd)
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

    >>> party = Party(name="Party")
    >>> party.save()

Create Lines to reschedule::

    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])

    >>> move = Move()
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal('90.00')
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.party = party
    >>> line.debit = Decimal('90.00')
    >>> line.second_currency = eur
    >>> line.amount_second_currency = Decimal('100.00')
    >>> line.maturity_date = period.start_date
    >>> move.save()

    >>> line, = [l for l in move.lines if l.account == receivable]
    >>> receivable.reload()
    >>> receivable.balance, receivable.amount_second_currency
    (Decimal('90.00'), Decimal('100.00'))

Split line by amount::

    >>> reschedule = Wizard('account.move.line.reschedule', [line])
    >>> reschedule.form.total_amount
    Decimal('100.00')
    >>> reschedule.form.start_date = period.end_date
    >>> reschedule.form.frequency = 'other'
    >>> reschedule.form.interval = 2
    >>> reschedule.form.amount = Decimal('30.00')
    >>> reschedule.execute('preview')

    >>> term1, term2, term3, term4 = reschedule.form.terms
    >>> term1.date == period.end_date
    True
    >>> term2.date == period.end_date + relativedelta(months=2)
    True
    >>> term3.date == period.end_date + relativedelta(months=4)
    True
    >>> term4.date == period.end_date + relativedelta(months=6)
    True
    >>> term1.amount, term2.amount, term3.amount, term4.amount
    (Decimal('30.00'), Decimal('30.00'), Decimal('30.00'), Decimal('10.00'))

Split line by number::

    >>> reschedule = Wizard('account.move.line.reschedule', [line])
    >>> reschedule.form.total_amount
    Decimal('100.00')
    >>> reschedule.form.start_date = period.end_date
    >>> reschedule.form.frequency = 'monthly'
    >>> reschedule.form.number = 3
    >>> reschedule.execute('preview')

    >>> reschedule.form.description = "Split 3 months"
    >>> term1, term2, term3 = reschedule.form.terms
    >>> term1.date == period.end_date
    True
    >>> term2.date == period.end_date + relativedelta(months=1)
    True
    >>> term3.date == period.end_date + relativedelta(months=2)
    True
    >>> term1.amount, term2.amount, term3.amount
    (Decimal('33.33'), Decimal('33.33'), Decimal('33.34'))
    >>> term1.amount = Decimal('40.00')
    >>> term2.amount = term3.amount = Decimal('30.00')
    >>> term3.date += relativedelta(months=1)

    >>> reschedule.execute('reschedule')
    >>> reschedule_move, = reschedule.actions[0]
    >>> reschedule_move.description
    'Split 3 months'

Check receivable::

    >>> receivable.reload()
    >>> receivable.balance, receivable.amount_second_currency
    (Decimal('90.00'), Decimal('100.00'))

    >>> lines = Line.find([
    ...     ('account', '=', receivable.id),
    ...     ('reconciliation', '=', None),
    ...     ], order=[('maturity_date', 'ASC')])
    >>> line1, line2, line3 = lines

    >>> line1.debit, line1.amount
    (Decimal('36.00'), Decimal('40.00'))
    >>> line1.maturity_date == period.end_date
    True

    >>> line2.debit, line2.amount
    (Decimal('27.00'), Decimal('30.00'))
    >>> line2.maturity_date == period.end_date + relativedelta(months=1)
    True

    >>> line3.debit, line3.amount
    (Decimal('27.00'), Decimal('30.00'))
    >>> line3.maturity_date == period.end_date + relativedelta(months=3)
    True
