==================================
Account Tax Cash Supplier Scenario
==================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('account_tax_cash', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> Tax = Model.get('account.tax')
    >>> TaxGroup = Model.get('account.tax.group')
    >>> TaxCode = Model.get('account.tax.code')
    >>> tax_group = TaxGroup(name="Supplier", code="SUP")
    >>> tax_group.save()
    >>> tax = create_tax(Decimal('.10'))
    >>> tax.group = tax_group
    >>> tax.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.supplier_tax_group_on_cash_basis.append(TaxGroup(tax_group.id))
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> len(invoice.tax_group_on_cash_basis)
    1
    >>> invoice.invoice_date = period.start_date
    >>> line = invoice.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> line.account = expense
    >>> line.taxes.extend([Tax(tax.id)])
    >>> invoice.click('post')
    >>> invoice.total_amount
    Decimal('110.00')
    >>> invoice.move.state
    'posted'

Check tax lines::

    >>> TaxLine = Model.get('account.tax.line')

    >>> lines = TaxLine.find([])
    >>> len(lines)
    2
    >>> all(l.on_cash_basis for l in lines)
    True
