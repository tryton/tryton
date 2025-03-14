===============================
Account Statement Rule Scenario
===============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     'account_statement_rule', create_company, create_chart)

Get company::

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> cash = accounts['cash']
    >>> tax = accounts['tax']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create statement rules::

    >>> Rule = Model.get('account.statement.rule')

    >>> rule1 = Rule(name="Rule 1")
    >>> rule1.company = company
    >>> rule1.amount_low = Decimal('10')
    >>> rule1.description = r"Party: *(?P<party>.*)"
    >>> line1 = rule1.lines.new()
    >>> line1.amount = "amount * 0.1"
    >>> line1.account = tax
    >>> line2 = rule1.lines.new()
    >>> line2.amount = "pending"
    >>> line2.account = receivable
    >>> rule1.save()

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
    >>> origin.description = "Party: %s" % customer.code
    >>> statement.save()
    >>> len(statement.lines)
    0

Apply rules on statement::

    >>> statement.click('apply_rules')
    >>> len(statement.lines)
    2
    >>> sorted([l.amount for l in statement.lines])
    [Decimal('5.00'), Decimal('45.00')]
    >>> assertEqual({l.account for l in statement.lines}, {tax, receivable})
    >>> assertEqual({l.party for l in statement.lines}, {None, customer})
