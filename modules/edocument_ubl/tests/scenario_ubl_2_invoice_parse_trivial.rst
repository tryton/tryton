===========================
UBL 2 Invoice Parse Trivial
===========================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules(
    ...     ['edocument_ubl', 'account_invoice'], create_company, create_chart)

    >>> EInvoice = Model.get('edocument.ubl.invoice')
    >>> Invoice = Model.get('account.invoice')

Setup company::

    >>> company = get_company()
    >>> company.party.name = 'North American Veeblefetzer'
    >>> company.party.save()

Create currency::

    >>> eur = get_currency('CAD')

Parse the UBL invoice::

    >>> with file_open(
    ...         'edocument_ubl/tests/UBL-Invoice-2.1-Example-Trivial.xml',
    ...         mode='rb') as fp:
    ...     invoice_id = EInvoice.parse(fp.read(), config.context)

    >>> invoice = Invoice(invoice_id)

    >>> assertEqual(invoice.invoice_date, dt.date(2011, 9, 22))
    >>> invoice.party.name
    'Custom Cotter Pins'
    >>> assertEqual(invoice.company, company)
    >>> invoice.total_amount
    Decimal('100.00')
    >>> line, = invoice.lines
    >>> line.description
    'Cotter pin, MIL-SPEC'
    >>> line.quantity
    1.0
    >>> line.unit
    >>> line.unit_price
    Decimal('100.0000')
