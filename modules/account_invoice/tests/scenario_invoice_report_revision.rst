================================
Invoice Report Revision Scenario
================================

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

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sequence = Model.get('ir.sequence')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Post an invoice::

    >>> invoice = Invoice()
    >>> invoice.type = 'out'
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check invoice report::

    >>> bool(invoice.invoice_report_cache)
    True
    >>> len(invoice.invoice_report_revisions)
    0
    >>> invoice.invoice_report_format
    'odt'

Execute update invoice report wizard::

    >>> refresh_invoice_report = Wizard(
    ...     'account.invoice.refresh_invoice_report', [invoice])
    >>> revision, = invoice.invoice_report_revisions
    >>> bool(revision.invoice_report_cache)
    True
    >>> revision.invoice_report_format
    'odt'
    >>> revision.filename
    'Invoice-1.odt'
