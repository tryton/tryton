=================================
Account Statement Origin Scenario
=================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_statement', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create a statement with origins::

    >>> AccountJournal = Model.get('account.journal')
    >>> StatementJournal = Model.get('account.statement.journal')
    >>> Statement = Model.get('account.statement')
    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> journal_number = StatementJournal(name="Number",
    ...     journal=account_journal,
    ...     account=cash,
    ...     validation='number_of_lines',
    ...     )
    >>> journal_number.save()

    >>> statement = Statement(name="number origins")
    >>> statement.journal = journal_number
    >>> statement.number_of_lines = 1
    >>> origin = statement.origins.new()
    >>> origin.date = today
    >>> origin.amount = Decimal('50.00')
    >>> origin.party = customer
    >>> statement.click('validate_statement')

Statement can not be posted until all origins are finished::

    >>> statement.click('post')
    Traceback (most recent call last):
        ...
    StatementPostError: ...
    >>> statement.click('draft')
    >>> origin, = statement.origins
    >>> line = origin.lines.new()
    >>> assertEqual(line.date, today)
    >>> line.amount
    Decimal('50.00')
    >>> assertEqual(line.party, customer)
    >>> assertEqual(line.account, receivable)
    >>> line.amount = Decimal('52.00')
    >>> line = origin.lines.new()
    >>> line.amount
    Decimal('-2.00')
    >>> line.account = expense
    >>> line.description = "Bank Fees"
    >>> statement.click('post')
    >>> statement.state
    'posted'

Test statement report::

    >>> report = Report('account.statement')
    >>> _ = report.execute([statement], {})

Test copy statement::

    >>> _ = statement.duplicate()
