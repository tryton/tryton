===================================
Account Tax Non Deductible Scenario
===================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts,
    ...     create_tax, create_tax_code)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_tax_non_deductible')

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

Create taxes::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> tax_non_deductible = create_tax(Decimal('.05'))
    >>> tax_non_deductible.non_deductible = True
    >>> tax_non_deductible.save()

    >>> base_code = create_tax_code(tax, 'base', 'invoice')
    >>> base_code.save()
    >>> tax_code = create_tax_code(tax, 'tax', 'invoice')
    >>> tax_code.save()
    >>> base_non_deductible_code = create_tax_code(
    ...     tax_non_deductible, 'base', 'invoice')
    >>> base_non_deductible_code.save()
    >>> tax_non_deductible_code = create_tax_code(
    ...     tax_non_deductible, 'tax', 'invoice')
    >>> tax_non_deductible_code.save()

Create party::

    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100.0000')
    >>> line.account = accounts['expense']
    >>> line.taxes_deductible_rate = Decimal('.50')
    >>> line.taxes.extend([tax, tax_non_deductible])
    >>> line.amount
    Decimal('110.00')
    >>> invoice.untaxed_amount
    Decimal('110.00')
    >>> invoice.tax_amount
    Decimal('5.00')
    >>> invoice.total_amount
    Decimal('115.00')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check tax code::

    >>> with config.set_context(periods=period_ids):
    ...     base_code = TaxCode(base_code.id)
    ...     tax_code = TaxCode(tax_code.id)
    ...     base_non_deductible_code = TaxCode(base_non_deductible_code.id)
    ...     tax_non_deductible_code = TaxCode(tax_non_deductible_code.id)
    >>> base_code.amount
    Decimal('50.00')
    >>> tax_code.amount
    Decimal('5.00')
    >>> base_non_deductible_code.amount
    Decimal('100.00')
    >>> tax_non_deductible_code.amount
    Decimal('5.00')
