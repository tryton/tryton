=======================================
Account Cash Rounding Purchase Scenario
=======================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules(['account_cash_rounding', 'purchase'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> Account = Model.get('account.account')
    >>> AccountConfig = Model.get('account.configuration')
    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

    >>> Configuration = Model.get('account.configuration')
    >>> config = Configuration(1)
    >>> config.default_category_account_expense = accounts['expense']
    >>> config.save()

Set cash rounding::

    >>> currency = company.currency
    >>> currency.cash_rounding = Decimal('0.05')
    >>> currency.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create purchase::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = party
    >>> line = purchase.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.07')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('42.07'), Decimal('0.00'), Decimal('42.07'))
    >>> purchase.cash_rounding = True
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('42.07'), Decimal('0.00'), Decimal('42.05'))
    >>> purchase.click('quote')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('42.07'), Decimal('0'), Decimal('42.05'))

Create invoice::

    >>> purchase.click('confirm')
    >>> invoice, = purchase.invoices
    >>> bool(invoice.cash_rounding)
    True
