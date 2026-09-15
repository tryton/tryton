=================================
Account Invoice Factur X Scenario
=================================

Imports::

    >>> from decimal import Decimal
    >>> from io import BytesIO
    >>> from unittest.mock import patch

    >>> import facturx

    >>> from proteus import Model, Report
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.invoice import InvoiceReport
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open

    >>> profile = globals().get('profile', 'urn:cen.eu:en16931:2017')

Activate modules::

    >>> config = activate_modules(
    ...     'account_invoice_factur_x', create_company, create_chart)

    >>> ActionReport = Model.get('ir.action.report')
    >>> Country = Model.get('country.country')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> UoM = Model.get('product.uom')

Patch invoice report convert::

    >>> with file_open('account_invoice_factur_x/tests/invoice.pdf', 'rb') as fp:
    ...     _ = patch.object(
    ...         InvoiceReport, 'convert', return_value=('pdf', fp.read())).start()

Set invoice report to PDF::

    >>> invoice_report, = ActionReport.find([
    ...         ('report_name', '=', 'account.invoice'),
    ...         ])
    >>> invoice_report.extension = 'pdf'
    >>> invoice_report.save()

Create country::

    >>> france = Country(name="France", code="FR")
    >>> france.save()

Setup company::

    >>> company = get_company()
    >>> address, = company.party.addresses
    >>> address.country = france
    >>> address.save()
    >>> identifier = company.party.identifiers.new(type='eu_vat')
    >>> identifier.code = "FR40303265045"
    >>> identifier.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('.20'))
    >>> tax.unece_code = 'VAT'
    >>> tax.unece_category_code = 'S'
    >>> tax.save()

Create party::

    >>> party = Party(name="Party")
    >>> party.factur_x_profile = profile
    >>> address, = party.addresses
    >>> address.country = france
    >>> party.save()

Create invoice::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> invoice = Invoice(type='out')
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.description = "Service"
    >>> line.quantity = 1
    >>> line.unit = unit
    >>> line.unit_price = Decimal('50.0000')
    >>> line.account = accounts['revenue']
    >>> line.taxes.append(tax)
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Print invoice::

    >>> pdf = Report('account.invoice').execute([invoice])[1]
    >>> filename, xml = facturx.get_facturx_xml_from_pdf(
    ...     BytesIO(pdf), check_schematron=False)
    >>> filename
    'factur-x.xml'
    >>> bool(xml)
    True
