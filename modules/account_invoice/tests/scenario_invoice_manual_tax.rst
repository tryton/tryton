==================
Invoice Manual Tax
==================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts, create_tax,
    ...     create_tax_code)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice')

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> TaxCode = Model.get('account.tax.code')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period_ids = [p.id for p in fiscalyear.periods]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> invoice_base_code = create_tax_code(tax, 'base', 'invoice')
    >>> invoice_base_code.save()
    >>> invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
    >>> invoice_tax_code.save()

Create party::

    >>> party = Party(name="Party")
    >>> party.save()

Post a supplier invoice with manual taxes::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> tax_line = invoice.taxes.new()
    >>> bool(tax_line.manual)
    True
    >>> tax_line.tax = tax
    >>> tax_line.base = Decimal('100')
    >>> tax_line.amount
    Decimal('10.00')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('0.00'), Decimal('10.00'), Decimal('10.00'))

Post invoice and check tax codes::

    >>> invoice.click('post')
    >>> invoice.untaxed_amount, invoice.tax_amount, invoice.total_amount
    (Decimal('0.00'), Decimal('10.00'), Decimal('10.00'))

    >>> with config.set_context(periods=period_ids):
    ...     invoice_base_code = TaxCode(invoice_base_code.id)
    ...     invoice_base_code.amount
    Decimal('100.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_tax_code = TaxCode(invoice_tax_code.id)
    ...     invoice_tax_code.amount
    Decimal('10.00')
