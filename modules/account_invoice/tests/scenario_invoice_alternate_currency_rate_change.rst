===============================================
Invoice Scenario Alternate Currency Rate Change
===============================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = dt.date.today()
    >>> tomorrow = today + dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('account_invoice')

    >>> Configuration = Model.get('account.configuration')
    >>> Invoice = Model.get('account.invoice')
    >>> Journal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')

Create company::

    >>> currency = get_currency('USD')
    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=currency)

Set alternate currency rates::

    >>> rate = eur.rates.new()
    >>> rate.date = today
    >>> rate.rate = Decimal('1.20')
    >>> rate = eur.rates.new()
    >>> rate.date = tomorrow
    >>> rate.rate = Decimal('1.10')
    >>> eur.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Configure currency exchange::

    >>> currency_exchange_account, = (
    ...     accounts['revenue'].duplicate(
    ...         default={'name': "Currency Exchange"}))
    >>> configuration = Configuration(1)
    >>> configuration.currency_exchange_credit_account = (
    ...     currency_exchange_account)
    >>> configuration.save()

Create payment method::

    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = "Cash"
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

Create party::

    >>> party = Party(name='Party')
    >>> party.save()

Create invoice with alternate currency::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.currency = eur
    >>> line = invoice.lines.new()
    >>> line.description = "Line"
    >>> line.account = accounts['revenue']
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('80')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.total_amount
    Decimal('400.00')

Pay the invoice::

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.amount
    Decimal('400.00')
    >>> pay.form.currency == eur
    True
    >>> pay.form.payment_method = payment_method
    >>> pay.form.date = tomorrow
    >>> pay.execute('choice')
    >>> pay.state
    'end'
    >>> invoice.state
    'paid'

    >>> accounts['receivable'].reload()
    >>> abs(accounts['receivable'].balance)
    Decimal('0.00')
    >>> currency_exchange_account.reload()
    >>> currency_exchange_account.balance
    Decimal('-30.31')
