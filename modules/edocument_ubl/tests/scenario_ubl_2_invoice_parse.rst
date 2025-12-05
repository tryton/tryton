===================
UBL 2 Invoice Parse
===================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, create_tax
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual
    >>> from trytond.tools import file_open

    >>> cash_rounding = globals().get('cash_rounding', False)

Activate modules::

    >>> modules = ['edocument_ubl', 'account_invoice', 'purchase']
    >>> if cash_rounding:
    ...     modules.append('account_cash_rounding')
    >>> config = activate_modules(modules, create_company, create_chart)

    >>> Attachment = Model.get('ir.attachment')
    >>> EInvoice = Model.get('edocument.ubl.invoice')
    >>> Invoice = Model.get('account.invoice')

Setup company::

    >>> company = get_company()
    >>> company.party.name = 'Buyercompany ltd'
    >>> company.party.save()

Create currency::

    >>> eur = get_currency('EUR')
    >>> if cash_rounding:
    ...     eur.cash_rounding = Decimal('1')
    >>> eur.save()

Create tax::

    >>> tax20 = create_tax(Decimal('.2'))
    >>> tax20.unece_category_code = 'S'
    >>> tax20.unece_code = 'VAT'
    >>> tax20.save()

    >>> tax10 = create_tax(Decimal('.1'))
    >>> tax10.unece_category_code = 'AA'
    >>> tax10.unece_code = 'VAT'
    >>> tax10.save()

    >>> tax0 = create_tax(Decimal('0'))
    >>> tax0.unece_category_code = 'E'
    >>> tax0.unece_code = 'VAT'
    >>> tax0.save()

Parse the UBL invoice::

    >>> with file_open(
    ...         'edocument_ubl/tests/UBL-Invoice-2.1-Example.xml',
    ...         mode='rb') as fp:
    ...     invoice_id = EInvoice.parse(fp.read(), config.context)

    >>> invoice = Invoice(invoice_id)

    >>> invoice.reference
    'TOSL108'
    >>> assertEqual(invoice.invoice_date, dt.date(2009, 12, 15))
    >>> invoice.party.name
    'Salescompany ltd.'
    >>> invoice.invoice_address.rec_name
    'Salescompany ltd., Main street 1 5467, 54321, Big city'
    >>> assertEqual(invoice.company, company)
    >>> assertEqual(
    ...     invoice.total_amount,
    ...     Decimal('1729.00') if cash_rounding else Decimal('1728.70'))
    >>> invoice.tax_amount
    Decimal('292.20')
    >>> len(invoice.lines)
    5

    >>> attachments = Attachment.find([])
    >>> len(attachments)
    3
    >>> assertEqual({a.resource for a in attachments}, {invoice})
    >>> sorted((a.name, a.type) for a in attachments)
    [('Drawing Doc2.pdf', 'data'), ('Framework agreement Contract321', 'data'), ('Timesheet Doc1', 'link')]
