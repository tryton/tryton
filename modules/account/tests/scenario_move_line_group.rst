====================
Group Lines Scenario
====================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account.exceptions import CancelDelegatedWarning

Activate modules::

    >>> config = activate_modules('account')

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
    >>> payable = accounts['payable']
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name="Party")
    >>> party.save()

Create Lines to group::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_expense, = Journal.find([
    ...         ('code', '=', 'EXP'),
    ...         ])

    >>> move = Move()
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.party = party
    >>> line.debit = Decimal(100)
    >>> line.second_currency = eur
    >>> line.amount_second_currency = Decimal(90)
    >>> line.maturity_date = period.start_date + dt.timedelta(days=2)
    >>> move.save()

    >>> move = Move()
    >>> move.journal = journal_expense
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = expense
    >>> line.debit = Decimal(50)
    >>> line = move.lines.new()
    >>> line.account = payable
    >>> line.party = party
    >>> line.credit = Decimal(50)
    >>> line.second_currency = eur
    >>> line.amount_second_currency = Decimal(45)
    >>> line.maturity_date = period.start_date + dt.timedelta(days=4)
    >>> move.save()

    >>> receivable.reload()
    >>> receivable.balance, receivable.amount_second_currency
    (Decimal('100.00'), Decimal('90.00'))
    >>> payable.reload()
    >>> payable.balance, payable.amount_second_currency
    (Decimal('-50.00'), Decimal('-45.00'))

Group lines::

    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

    >>> Line = Model.get('account.move.line')
    >>> lines = Line.find([('account', 'in', [payable.id, receivable.id])])
    >>> len(lines)
    2
    >>> group = Wizard('account.move.line.group', lines)
    >>> group.form.journal = journal_cash
    >>> group.form.description = "Group lines"
    >>> group.execute('group')

    >>> receivable.reload()
    >>> receivable.balance, receivable.amount_second_currency
    (Decimal('50.00'), Decimal('45.00'))
    >>> payable.reload()
    >>> payable.balance, payable.amount_second_currency
    (Decimal('0.00'), Decimal('0.00'))

    >>> delegated_line1, delegated_line2 = lines
    >>> delegated_line1.reload()
    >>> delegated_line2.reload()
    >>> delegated_line1.delegated_amount
    Decimal('45')
    >>> delegated_line2.delegated_amount
    Decimal('45')

    >>> Reconciliation = Model.get('account.move.reconciliation')
    >>> reconciliations = Reconciliation.find([])
    >>> len(reconciliations)
    2
    >>> all(r.delegate_to for r in reconciliations)
    True
    >>> delegate_to = reconciliations[0].delegate_to
    >>> delegate_to.account == receivable
    True
    >>> delegate_to.debit
    Decimal('50')
    >>> delegate_to.maturity_date == period.start_date + dt.timedelta(days=2)
    True
    >>> delegate_to.move_description
    'Group lines'

Cancelling the delegation move::

   >>> delegation_move = delegate_to.move
   >>> cancel = Wizard('account.move.cancel', [delegation_move])
   >>> try:
   ...   cancel.execute('cancel')
   ... except CancelDelegatedWarning as warning:
   ...   _, (key, *_) = warning.args
   ...   raise  # doctest: +IGNORE_EXCEPTION_DETAIL
   Traceback (most recent call last):
      ...
   CancelDelegatedWarning: ...

   >>> Warning = Model.get('res.user.warning')
   >>> Warning(user=config.user, name=key).save()
   >>> cancel.execute('cancel')
   >>> Reconciliation.find([('id', '=', reconciliations[0].id)])
   []

   >>> delegated_line1.reload()
   >>> delegated_line1.delegated_amount
