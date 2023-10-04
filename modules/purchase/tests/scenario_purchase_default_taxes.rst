===========================
Purchase with Default Taxes
===========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts, create_tax)

Activate modules::

    >>> config = activate_modules('purchase')

    >>> Party = Model.get('party.party')
    >>> Purchase = Model.get('purchase.purchase')
    >>> Tax = Model.get('account.tax')

Create company::

    >>> _ = create_company()

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> accounts['expense'].taxes.append(Tax(tax.id))
    >>> accounts['expense'].save()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create a purchase without product::

    >>> purchase = Purchase(party=supplier)
    >>> line = purchase.lines.new()
    >>> line.taxes == [tax]
    True
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100.0000')
    >>> purchase.click('quote')
    >>> purchase.total_amount
    Decimal('110.00')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Check invoice::

    >>> invoice, = purchase.invoices
    >>> invoice.total_amount
    Decimal('110.00')
    >>> line, = invoice.lines
    >>> line.account == accounts['expense']
    True
