=======================
Sale with Default Taxes
=======================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_tax, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('sale')

    >>> Party = Model.get('party.party')
    >>> Sale = Model.get('sale.sale')
    >>> Tax = Model.get('account.tax')

Create company::

    >>> _ = create_company()

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> accounts['revenue'].taxes.append(Tax(tax.id))
    >>> accounts['revenue'].save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create a sale without product::

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new()
    >>> assertEqual(line.taxes, [tax])
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100.0000')
    >>> sale.click('quote')
    >>> sale.total_amount
    Decimal('110.00')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice::

    >>> invoice, = sale.invoices
    >>> invoice.total_amount
    Decimal('110.00')
    >>> line, = invoice.lines
    >>> assertEqual(line.account, accounts['revenue'])
