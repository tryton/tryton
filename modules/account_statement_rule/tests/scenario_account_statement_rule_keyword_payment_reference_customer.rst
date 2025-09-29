==================================================================
Account Statement Rule Keyword Payment Reference Customer Scenario
==================================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_statement_rule'],
    ...     create_company, create_chart)

    >>> AccountConfiguration = Model.get('account.configuration')
    >>> AccountJournal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> Rule = Model.get('account.statement.rule')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Get accounts::

    >>> accounts = get_accounts()

    >>> account_configuration = AccountConfiguration(1)
    >>> account_configuration.customer_payment_reference_number = 'party'
    >>> account_configuration.save()

Create a party::

    >>> customer = Party(name="Customer", code="CUST-001")
    >>> customer.save()

Create statement rules::

    >>> rule = Rule(name="Payment Reference Rule")
    >>> rule.description = r"Ref: *(?P<payment_reference>.*)"
    >>> line = rule.lines.new()
    >>> line.amount = "pending"
    >>> rule.save()

Create a statement::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> journal_number = StatementJournal(
    ...     name="Number",
    ...     journal=account_journal,
    ...     account=accounts['cash'],
    ...     validation='number_of_lines')
    >>> journal_number.save()

    >>> statement = Statement(name="Test")
    >>> statement.journal = journal_number
    >>> statement.number_of_lines = 1
    >>> origin = statement.origins.new()
    >>> origin.date = today
    >>> origin.amount = Decimal('50.00')
    >>> origin.description = "Ref: RF92CUST001"
    >>> statement.click('apply_rules')
    >>> line, = statement.lines
    >>> assertEqual(line.party, customer)
