=========================
Account FR Chorus Invoice
=========================

Imports::

    >>> import datetime as dt
    >>> import os
    >>> import time
    >>> import uuid
    >>> from decimal import Decimal
    >>> from functools import partial
    >>> from unittest.mock import patch

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.party.party import Identifier
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Patch SIRET validation::

    >>> mock = patch.object(
    ...     Identifier, 'check_code',
    ...     return_value=None).start()

Activate modules::

    >>> config = activate_modules([
    ...     'account_fr_chorus', 'edocument_uncefact', 'account_fr'],
    ...     create_company, partial(create_chart, chart='account_fr.root'))

    >>> AccountConfig = Model.get('account.configuration')
    >>> Cron = Model.get('ir.cron')
    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceChorus = Model.get('account.invoice.chorus')
    >>> Party = Model.get('party.party')
    >>> Tax = Model.get('account.tax')

Setup company::

    >>> company = get_company()
    >>> company_party = company.party
    >>> company_address, = company_party.addresses
    >>> company_address.postal_code = '99999'
    >>> company_address.street = "Street"
    >>> company_address.city = "City"
    >>> siret = company_party.identifiers.new(type='fr_siret')
    >>> siret.code = os.getenv('CHORUS_COMPANY_SIRET')
    >>> siret.address = company_address
    >>> company_party.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> acccounts = get_accounts()

    >>> tax, = Tax.find([
    ...         ('group.kind', '=', 'sale'),
    ...         ('name', 'ilike', '%normal%'),
    ...         ], limit=1)

Configure Chorus::

    >>> account_config = AccountConfig(1)
    >>> account_config.chorus_piste_client_id = os.getenv(
    ...     'CHORUS_PISTE_CLIENT_ID')
    >>> account_config.chorus_piste_client_secret = os.getenv(
    ...     'CHORUS_PISTE_CLIENT_SECRET')
    >>> account_config.chorus_login = os.getenv(
    ...     'CHORUS_LOGIN')
    >>> account_config.chorus_password = os.getenv(
    ...     'CHORUS_PASSWORD')
    >>> account_config.chorus_service = 'service-qualif'
    >>> account_config.chorus_syntax = 'edocument.uncefact.invoice'
    >>> account_config.save()

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.chorus = True
    >>> customer.save()
    >>> customer_address, = customer.addresses
    >>> customer_address.street = "Street"
    >>> siret = customer.identifiers.new(type='fr_siret')
    >>> siret.code = os.getenv('CHORUS_CUSTOMER_SIRET')
    >>> siret.address = customer_address
    >>> customer.save()

Create invoice::

    >>> invoice = Invoice(type='out', party=customer)
    >>> line = invoice.lines.new()
    >>> line.account = acccounts['revenue']
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('50.0000')
    >>> line.taxes.append(tax)
    >>> invoice.save()
    >>> Invoice.write([invoice], {
    ...         'number': str(uuid.uuid4())[:20],
    ...         'invoice_date': today,
    ...         }, config._context)
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check Chorus invoice::

    >>> invoice_chorus, = InvoiceChorus.find([])
    >>> invoice_chorus.syntax
    'edocument.uncefact.invoice'
    >>> invoice_chorus.number
    >>> invoice_chorus.date

Send to Chorus::

    >>> invoice_chorus.click('send')
    >>> invoice_chorus.state
    'sent'
    >>> bool(invoice_chorus.number)
    True
    >>> bool(invoice_chorus.date)
    True
    >>> bool(invoice_chorus.data)
    True
    >>> number = invoice_chorus.number

Update from Chorus::

    >>> while invoice_chorus.state == 'sent':
    ...     invoice_chorus.click('update')
    ...     time.sleep(1)
    >>> invoice_chorus.state
    'exception'

Add code to tax::

    >>> tax.template_override = True
    >>> tax.unece_code = 'VAT'
    >>> tax.unece_category_code = 'S'
    >>> for child in tax.childs:
    ...     child.template_override = True
    ...     child.unece_code = tax.unece_code
    ...     child.unece_category_code = tax.unece_category_code
    >>> tax.save()

Resend to Chorus::

    >>> invoice_chorus.click('send')
    >>> invoice_chorus.state
    'sent'
    >>> invoice_chorus.number != number
    True

Update from Chorus::

    >>> while invoice_chorus.state == 'sent':
    ...     invoice_chorus.click('update')
    ...     time.sleep(1)
    >>> invoice_chorus.state
    'done'
