=================
Invoice in Future
=================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (create_company,
    ...     get_company)
    >>> from trytond.modules.account.tests.tools import (create_fiscalyear,
    ...     create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = datetime.date.today()
    >>> tomorrow = today + datetime.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('account_invoice')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)

Posting an invoice in the future raises a warning::

    >>> invoice.invoice_date = tomorrow
    >>> invoice.click('post')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    InvoiceFutureWarning: ...

Post invoice::

    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
