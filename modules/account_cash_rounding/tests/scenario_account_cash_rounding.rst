==============================
Account Cash Rounding Scenario
==============================

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

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

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

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> delta, = line.relativedeltas
    >>> delta.days = 20
    >>> line = payment_term.lines.new(type='remainder')
    >>> delta = line.relativedeltas.new(days=40)
    >>> payment_term.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> bool(invoice.cash_rounding)
    True
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.06')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('42.06'), Decimal('0.00'), Decimal('42.10'))
    >>> invoice.cash_rounding = False
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('42.06'), Decimal('0.00'), Decimal('42.06'))
    >>> invoice.cash_rounding = True
    >>> invoice.save()
    >>> invoice.total_amount
    Decimal('42.10')

Post invoice::

    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('42.10')

    >>> cash_rounding_credit.reload()
    >>> cash_rounding_credit.credit
    Decimal('0.04')
