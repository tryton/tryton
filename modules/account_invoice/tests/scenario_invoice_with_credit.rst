============================
Invoice with credit Scenario
============================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice')

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

    >>> TaxCode = Model.get('account.tax.code')
    >>> Tax = Model.get('account.tax')
    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> invoice_base_code = create_tax_code(tax, 'base', 'invoice')
    >>> invoice_base_code.save()
    >>> invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
    >>> invoice_tax_code.save()
    >>> credit_note_base_code = create_tax_code(tax, 'base', 'credit')
    >>> credit_note_base_code.save()
    >>> credit_note_tax_code = create_tax_code(tax, 'tax', 'credit')
    >>> credit_note_tax_code.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('10.0000')
    >>> line.taxes.append(Tax(tax.id))
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = -2
    >>> line.unit_price = Decimal('5.0000')
    >>> line.taxes.append(Tax(tax.id))
    >>> invoice.click('post')

    >>> invoice.untaxed_amount
    Decimal('40.00')
    >>> invoice.tax_amount
    Decimal('4.00')
    >>> invoice.total_amount
    Decimal('44.00')

Test taxes::

    >>> len(invoice.taxes)
    2

    >>> accounts['tax'].reload()
    >>> accounts['tax'].debit, accounts['tax'].credit
    (Decimal('1.00'), Decimal('5.00'))

    >>> with config.set_context(periods=period_ids):
    ...     invoice_base_code = TaxCode(invoice_base_code.id)
    ...     invoice_base_code.amount
    Decimal('50.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_tax_code = TaxCode(invoice_tax_code.id)
    ...     invoice_tax_code.amount
    Decimal('5.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_base_code = TaxCode(credit_note_base_code.id)
    ...     credit_note_base_code.amount
    Decimal('10.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_tax_code = TaxCode(credit_note_tax_code.id)
    ...     credit_note_tax_code.amount
    Decimal('1.00')
