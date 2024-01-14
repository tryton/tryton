=====================================
Deposit with Second Currency Scenario
=====================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_deposit.tests.tools import add_deposit_accounts
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('account_deposit')

    >>> Party = Model.get('party.party')
    >>> Invoice = Model.get('account.invoice')

Create company::

    >>> currency = get_currency('USD')
    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=currency)

Set alternate currency rates::

    >>> rate = eur.rates.new()
    >>> rate.date = yesterday
    >>> rate.rate = Decimal('1.20')
    >>> rate = eur.rates.new()
    >>> rate.date = today
    >>> rate.rate = Decimal('1.10')
    >>> eur.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = add_deposit_accounts(get_accounts())
    >>> accounts['deposit'].second_currency = eur
    >>> accounts['deposit'].save()

Create party::

    >>> party = Party(name='Party')
    >>> party.save()

Create deposit invoice::

    >>> invoice = Invoice(party=party, currency=eur, invoice_date=yesterday)
    >>> line = invoice.lines.new()
    >>> line.account = accounts['deposit']
    >>> line.description = "Deposit"
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(100)
    >>> invoice.click('post')
    >>> invoice.untaxed_amount
    Decimal('100.00')

Check party deposit::

    >>> party.reload()
    >>> party.deposit
    Decimal('83.33')

Create final invoice::

    >>> invoice = Invoice(party=party, currency=eur, invoice_date=today)
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.description = "Revenue"
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(500)
    >>> invoice.save()
    >>> invoice.untaxed_amount
    Decimal('500.00')

Recall deposit::

    >>> recall_deposit = invoice.click('recall_deposit')
    >>> recall_deposit.form.account = accounts['deposit']
    >>> recall_deposit.form.description = "Recall Deposit"
    >>> recall_deposit.execute('recall')
    >>> invoice.reload()
    >>> deposit_line, = [l for l in invoice.lines
    ...     if l.account == accounts['deposit']]
    >>> deposit_line.amount
    Decimal('-100.00')
    >>> invoice.untaxed_amount
    Decimal('400.00')
    >>> invoice.click('post')

Check party deposit::

    >>> party.reload()
    >>> party.deposit
    Decimal('-7.58')
    >>> accounts['deposit'].reload()
    >>> accounts['deposit'].balance
    Decimal('7.58')
    >>> accounts['deposit'].amount_second_currency
    Decimal('0.00')
