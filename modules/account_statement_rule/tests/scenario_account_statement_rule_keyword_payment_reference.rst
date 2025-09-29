=========================================================
Account Statement Rule Keyword Payment Reference Scenario
==========================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_statement_rule'],
    ...     create_company, create_chart)

    >>> AccountConfiguration = Model.get('account.configuration')
    >>> AccountJournal = Model.get('account.journal')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> Rule = Model.get('account.statement.rule')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

    >>> account_configuration = AccountConfiguration(1)
    >>> account_configuration.customer_payment_reference_number = 'invoice'
    >>> account_configuration.save()

Create a party::

    >>> customer = Party(name="Customer", code="CUST-001")
    >>> customer.save()

Create an invoice::

    >>> invoice = Invoice(party=customer)
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('40.0000')
    >>> line.account = accounts['revenue']
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

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
    >>> origin.description = "Ref: " + invoice.customer_payment_reference
    >>> statement.click('apply_rules')
    >>> line, = statement.lines
    >>> assertEqual(line.related_to, invoice)
    >>> assertEqual(line.party, customer)
    >>> assertEqual(line.account, invoice.account)
