===================================
Account Cash Rounding Sale Scenario
===================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import create_payment_term
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     ['account_cash_rounding', 'account_invoice', 'sale'],
    ...     create_company, create_chart)

    >>> Account = Model.get('account.account')
    >>> AccountConfig = Model.get('account.configuration')

Get accounts::

    >>> accounts = get_accounts()

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

    >>> currency = get_currency()
    >>> currency.cash_rounding = Decimal('0.05')
    >>> currency.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = party
    >>> sale.payment_term = payment_term
    >>> line = sale.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.02')
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('42.02'), Decimal('0.00'), Decimal('42.00'))
    >>> sale.click('quote')
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('42.02'), Decimal('0'), Decimal('42.00'))
