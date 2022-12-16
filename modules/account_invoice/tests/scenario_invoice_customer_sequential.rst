===========================
Customer Invoice Sequential
===========================

Imports::

    >>> from decimal import Decimal
    >>> import datetime as dt
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = dt.date.today()
    >>> past_year = today - relativedelta(years=1)

Activate modules::

    >>> config = activate_modules('account_invoice')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal years::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today=past_year))
    >>> fiscalyear.click('create_period')
    >>> next_fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today=today))
    >>> next_fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

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

    >>> invoice.click('post')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    InvoiceNumberError: ...

Post invoice on the third period::

    >>> invoice.invoice_date = fiscalyear.periods[2].start_date
    >>> invoice.click('post')
