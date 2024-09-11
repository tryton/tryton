===========================
Customer Invoice Sequential
===========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> past_year = today - dt.timedelta(days=365)

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

Create fiscal years::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=past_year))
    >>> fiscalyear.click('create_period')

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.execute('create_')
    >>> next_fiscalyear, = renew_fiscalyear.actions[0]

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice invoice second period and next year::

    >>> Invoice = Model.get('account.invoice')

    >>> invoice = Invoice(type='out')
    >>> invoice.party = party
    >>> invoice.invoice_date = fiscalyear.periods[1].start_date
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10')
    >>> line.account = accounts['revenue']
    >>> invoice.click('post')

    >>> invoice = Invoice(type='out')
    >>> invoice.party = party
    >>> invoice.invoice_date = next_fiscalyear.periods[0].start_date
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('20')
    >>> line.account = accounts['revenue']
    >>> invoice.click('post')

Try to post invoice on first period::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = party
    >>> invoice.invoice_date = fiscalyear.periods[0].start_date
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('5')
    >>> line.account = accounts['revenue']
    >>> invoice.save()

    >>> invoice.click('post')
    Traceback (most recent call last):
        ...
    InvoiceNumberError: ...

Post invoice on the third period::

    >>> invoice.invoice_date = fiscalyear.periods[2].start_date
    >>> invoice.click('post')
