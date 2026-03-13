=============================
Invoice Check Source Scenario
=============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create party::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create invoice::

    >>> invoice = Invoice(type='in', party=supplier)
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(10)
    >>> line.account = accounts['expense']
    >>> line.taxes.append(tax)
    >>> invoice.save()

    >>> Invoice.write([invoice.id], {
    ...         'source_untaxed_amount': Decimal('100.00'),
    ...         'source_tax_amount': Decimal('10.00'),
    ...         'source_total_amount': Decimal('110.00'),
    ...         }, invoice._context)

Try to validate::

    >>> invoice.click('validate_invoice')
    Traceback (most recent call last):
        ...
    InvoiceValidationError: ...

Correct quantity::

    >>> line, = invoice.lines
    >>> line.quantity = 10
    >>> invoice.click('validate_invoice')
    >>> invoice.state
    'validated'
