=========================================
Account Statement Second Currency Invoice
=========================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_statement', 'account_invoice'],
    ...     create_company, create_chart)

    >>> AccountConfiguration = Model.get('account.configuration')
    >>> AccountJournal = Model.get('account.journal')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Get currencies::

    >>> usd = get_currency('USD')
    >>> eur = get_currency('EUR')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Configure currency exchange::

    >>> currency_exchange_account, = (
    ...     accounts['revenue'].duplicate(
    ...         default={'name': "Currency Exchange"}))
    >>> account_configuration = AccountConfiguration(1)
    >>> account_configuration.currency_exchange_debit_account = (
    ...     currency_exchange_account)
    >>> account_configuration.save()

Create party::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create customer invoice in alternate currency::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> invoice.currency = eur
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('50.0000')
    >>> line.account = accounts['revenue']
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Post statement in company currency with second currency::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> statement_journal = StatementJournal(
    ...     name="Statement Journal", journal=account_journal,
    ...     currency=usd, account=accounts['cash'])
    >>> statement_journal.save()

    >>> statement = Statement(
    ...     name="Test", journal=statement_journal,
    ...     start_balance=Decimal('0.00'), end_balance=Decimal('20.00'))
    >>> line = statement.lines.new()
    >>> line.number = "1"
    >>> line.date = today
    >>> line.party = customer
    >>> line.amount = Decimal('20.00')
    >>> line.amount_second_currency = Decimal('50.00')
    >>> line.second_currency = eur
    >>> line.related_to = invoice
    >>> statement.click('validate_statement')
    >>> statement.state
    'validated'

Check invoice is paid::

    >>> invoice.reload()
    >>> invoice.state
    'paid'
