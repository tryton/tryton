===============================
Account Tax Cash Closing Period
===============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Activate modules::

    >>> config = activate_modules('account_tax_cash')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_cash = accounts['cash']

Set tax cash basis::

    >>> Tax = Model.get('account.tax')
    >>> TaxGroup = Model.get('account.tax.group')
    >>> TaxCode = Model.get('account.tax.code')

    >>> group_cash_basis = TaxGroup(name="Cash Basis", code="CASH")
    >>> group_cash_basis.save()

    >>> fiscalyear.tax_group_on_cash_basis.append(TaxGroup(group_cash_basis.id))
    >>> fiscalyear.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create revenue::

    >>> Move = Model.get('account.move')
    >>> Journal = Model.get('account.journal')
    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')])
    >>> move = Move()
    >>> move.period = period
    >>> move.date = period.start_date
    >>> move.journal = journal_revenue
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal('10')
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.party = party
    >>> line.debit = Decimal('10')
    >>> move.click('post')

Can close the period::

    >>> period.click('close')
    >>> period.click('reopen')

Receive cash::

    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> move = Move()
    >>> move.period = period
    >>> move.date = period.start_date
    >>> move.journal = journal_cash
    >>> line = move.lines.new()
    >>> line.account = account_cash
    >>> line.debit = Decimal('10')
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.party = party
    >>> line.credit = Decimal('10')
    >>> move.click('post')

Can not close the period::

    >>> period.click('close')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    ClosePeriodWarning: ...

Reconcile lines::

    >>> Line = Model.get('account.move.line')
    >>> lines = Line.find([('account', '=', receivable.id)])
    >>> reconcile_lines = Wizard('account.move.reconcile_lines', lines)
    >>> reconcile_lines.state == 'end'
    True

Can close the period::

    >>> period.click('close')
