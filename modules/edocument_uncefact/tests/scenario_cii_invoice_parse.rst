=================
CII Invoice Parse
=================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, create_tax
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

Activate modules::

    >>> modules = ['edocument_uncefact', 'account_invoice', 'bank', 'purchase']
    >>> config = activate_modules(modules, create_company, create_chart)

    >>> EInvoice = Model.get('edocument.uncefact.invoice')
    >>> Invoice = Model.get('account.invoice')
    >>> UoM = Model.get('product.uom')

Setup company::

    >>> company = get_company()
    >>> company.party.name = 'ODIN 59'
    >>> company.party.save()

Create currency::

    >>> eur = get_currency('EUR')
    >>> eur.save()

Create tax::

    >>> tax21 = create_tax(Decimal('.21'))
    >>> tax21.unece_category_code = 'S'
    >>> tax21.unece_code = 'VAT'
    >>> tax21.save()

    >>> tax6 = create_tax(Decimal('.06'))
    >>> tax6.unece_category_code = 'S'
    >>> tax6.unece_code = 'VAT'
    >>> tax6.save()

Create unit::

    >>> uom, = UoM.find([('name', '=', "Unit")])
    >>> _ = uom.duplicate({'name': "piece", 'unece_code': 'H87'})

Parse the CII::

    >>> with file_open(
    ...         'edocument_uncefact/tests/CII_example1.xml',
    ...         mode='rb') as fp:
    ...     invoice_id = EInvoice.parse(fp.read(), {**config.context, 'company': None})

    >>> invoice = Invoice(invoice_id)
    >>> invoice.reference
    '12115118'
    >>> assertEqual(invoice.invoice_date, dt.date(2015, 1, 9))
    >>> invoice.party.name
    'De Koksmaat'
    >>> invoice.invoice_address.rec_name
    'De Koksmaat, Postbus 7l, 1950 AB, Velsen-Noord'
    >>> assertEqual(invoice.company, company)
    >>> invoice.total_amount
    Decimal('250.33')
    >>> invoice.tax_amount
    Decimal('20.73')
    >>> assertEqual(invoice.source_untaxed_amount, Decimal('229.60'))
    >>> assertEqual(invoice.source_tax_amount, Decimal('20.73'))
    >>> assertEqual(invoice.source_total_amount, Decimal('250.33'))
    >>> len(invoice.lines)
    20

    >>> payment_mean, = invoice.payment_means
    >>> account_number, = payment_mean.instrument.numbers
    >>> account_number.number
    'NL57 RABO 0107 3075 10'
    >>> assertEqual(payment_mean.instrument.owners, [invoice.party])
