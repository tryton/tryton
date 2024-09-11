=================================================
Account Cash Rounding Alternate Currency Scenario
=================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     ['account_cash_rounding', 'account_invoice'], create_company, create_chart)

    >>> Account = Model.get('account.account')
    >>> AccountConfig = Model.get('account.configuration')
    >>> Configuration = Model.get('account.configuration')

Set alternate currencies::

    >>> currency = get_currency('USD')
    >>> eur = get_currency('EUR')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Configure currency exchange::

    >>> currency_exchange_account, = (
    ...     accounts['revenue'].duplicate(
    ...         default={'name': "Currency Exchange"}))
    >>> configuration = Configuration(1)
    >>> configuration.currency_exchange_debit_account = (
    ...     currency_exchange_account)
    >>> configuration.save()

Set cash rounding::

    >>> cash_rounding_credit = Account(name="Cash Rounding")
    >>> cash_rounding_credit.type = accounts['revenue'].type
    >>> cash_rounding_credit.deferral = True
    >>> cash_rounding_credit.save()
    >>> cash_rounding_debit = Account(name="Cash Rounding")
    >>> cash_rounding_debit.type = accounts['expense'].type
    >>> cash_rounding_debit.deferral = True
    >>> cash_rounding_debit.save()
    >>> account_config = AccountConfig(1)
    >>> account_config.cash_rounding = True
    >>> account_config.cash_rounding_credit_account = cash_rounding_credit
    >>> account_config.cash_rounding_debit_account = cash_rounding_debit
    >>> account_config.save()

    >>> eur.cash_rounding = Decimal('0.05')
    >>> eur.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name="Party")
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.cash_rounding = True
    >>> invoice.currency = eur
    >>> bool(invoice.cash_rounding)
    True
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.06')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('42.06'), Decimal('0.00'), Decimal('42.05'))
    >>> invoice.save()
    >>> invoice.total_amount
    Decimal('42.05')

Post invoice::

    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('42.05')

    >>> cash_rounding_credit.reload()
    >>> cash_rounding_credit.credit, cash_rounding_credit.debit
    (Decimal('0.00'), Decimal('0.00'))

    >>> line_to_pay, = invoice.lines_to_pay
    >>> line_to_pay.debit, line_to_pay.credit
    (Decimal('21.02'), Decimal('0'))
    >>> line_to_pay.amount_second_currency
    Decimal('42.05')
