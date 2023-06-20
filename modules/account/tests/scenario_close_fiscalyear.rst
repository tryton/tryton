=================================
Account Close Fiscalyear Scenario
=================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.currency.tests.tools import get_currency

    >>> today = dt.date.today()
    >>> last_year = today - relativedelta(years=1)

Activate modules::

    >>> config = activate_modules('account')

    >>> Account = Model.get('account.account')
    >>> AccountType = Model.get('account.account.type')
    >>> Journal = Model.get('account.journal')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> Period = Model.get('account.period')
    >>> Sequence = Model.get('ir.sequence')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company, today=last_year)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Prepare the closing settings for fiscalyear close::

    >>> journal_sequence, = Sequence.find([
    ...        ('sequence_type.name', '=', "Account Journal"),
    ...     ], limit=1)
    >>> journal_closing = Journal()
    >>> journal_closing.name = 'Closing'
    >>> journal_closing.code = 'CLO'
    >>> journal_closing.type = 'situation'
    >>> journal_closing.sequence = journal_sequence
    >>> journal_closing.save()
    >>> period_closing = Period()
    >>> period_closing.name = 'Closing'
    >>> period_closing.start_date = fiscalyear.end_date
    >>> period_closing.end_date = fiscalyear.end_date
    >>> period_closing.fiscalyear = fiscalyear
    >>> period_closing.type = 'adjustment'
    >>> period_closing.save()
    >>> type_equity, = AccountType.find([('name', '=', "Equity")])

    >>> account_pl = Account()
    >>> account_pl.name = 'P&L'
    >>> account_pl.type = type_equity
    >>> account_pl.parent = accounts['revenue'].parent
    >>> account_pl.save()

Create children accounts::

    >>> receivable_customer = Account()
    >>> receivable_customer.name = "Customer Receivable"
    >>> receivable_customer.parent = accounts['receivable']
    >>> receivable_customer.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create and post a move using children accounts::

    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable_customer
    >>> line.debit = Decimal(21)
    >>> line.party = customer
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.debit = Decimal(21)
    >>> line.party = customer
    >>> move.save()
    >>> move.click('post')

Balance non deferral::

    >>> balance_non_deferral = Wizard('account.fiscalyear.balance_non_deferral')
    >>> balance_non_deferral.form.fiscalyear = fiscalyear
    >>> balance_non_deferral.form.journal = journal_closing
    >>> balance_non_deferral.form.period = period_closing
    >>> balance_non_deferral.form.credit_account = account_pl
    >>> balance_non_deferral.form.debit_account = account_pl
    >>> balance_non_deferral.execute('balance')
    >>> move, = Move.find([('state', '=', 'draft')])
    >>> move.click('post')

Renew fiscalyear using the wizard::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = False
    >>> renew_fiscalyear.execute('create_')

Check receivable balance before closing fiscalyear::

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('42.00')
    >>> receivable_customer.reload()
    >>> receivable_customer.balance
    Decimal('21.00')

Close fiscalyear::

    >>> fiscalyear.click('close')
    >>> fiscalyear.state
    'closed'

Check receivable amounts after closing fiscalyear::

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('42.00')
    >>> receivable_customer.reload()
    >>> receivable_customer.balance
    Decimal('21.00')
