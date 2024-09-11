=================================================
Invoice Scenario Alternate Currency with Exchange
=================================================

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

    >>> config = activate_modules('account_invoice', create_company, create_chart)

    >>> Configuration = Model.get('account.configuration')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')

Get currencies::

    >>> currency = get_currency('USD')
    >>> eur = get_currency('EUR')

Set alternate currency rates::

    >>> rate, = eur.rates
    >>> rate.rate = Decimal('0.3')
    >>> eur.save()

Create fiscal years::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Configure currency exchange::

    >>> currency_exchange_account, = (
    ...     accounts['revenue'].duplicate(
    ...         default={'name': "Currency Exchange"}))
    >>> configuration = Configuration(1)
    >>> configuration.currency_exchange_credit_account = (
    ...     currency_exchange_account)
    >>> configuration.save()

Create payment term::

    >>> payment_term = PaymentTerm(name="Payment Term")
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> line = payment_term.lines.new(type='remainder')
    >>> payment_term.save()

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Create invoice::

    >>> invoice = Invoice(party=party)
    >>> invoice.currency = eur
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100.0000')
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.total_amount
    Decimal('100.00')

Check accounts::

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('333.34')
    >>> accounts['receivable'].amount_second_currency
    Decimal('100.00')

    >>> currency_exchange_account.reload()
    >>> currency_exchange_account.balance
    Decimal('-0.01')
