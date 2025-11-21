=========================
EDocument Peppol Scenario
=========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('edocument_peppol', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> Peppol = Model.get('edocument.peppol')
    >>> PeppolService = Model.get('edocument.peppol.service')

Get accounts::

    >>> accounts = get_accounts()

Create a service::

    >>> peppol_service1 = PeppolService(sequence=1)
    >>> peppol_service1.types = []
    >>> peppol_service1.save()
    >>> peppol_service2 = PeppolService(sequence=2)
    >>> peppol_service2.types = ['bis-billing-3']
    >>> peppol_service2.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create a customer::

    >>> customer = Party(name="Customer")
    >>> customer.peppol_types = ['bis-billing-3']
    >>> customer.save()

Post an invoice::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100.0000')
    >>> line.account = accounts['revenue']
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check the Peppol invoice::

    >>> peppol, = Peppol.find([])
    >>> peppol.direction
    'out'
    >>> assertEqual(peppol.company, invoice.company)
    >>> peppol.type
    'bis-billing-3'
    >>> assertEqual(peppol.invoice, invoice)
    >>> assertEqual(peppol.service, peppol_service2)
    >>> bool(peppol.data)
    True
    >>> peppol.state
    'processing'
