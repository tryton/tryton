=======================
Purchase Empty Scenario
=======================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('purchase', create_company, create_chart)

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create empty purchase::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.click('quote')
    >>> purchase.state
    'quotation'
    >>> purchase.untaxed_amount
    Decimal('0')
    >>> purchase.tax_amount
    Decimal('0')
    >>> purchase.total_amount
    Decimal('0')
    >>> purchase.click('confirm')
    >>> purchase.state
    'done'
    >>> purchase.shipment_state
    'none'
    >>> len(purchase.moves)
    0
    >>> len(purchase.shipment_returns)
    0
    >>> purchase.invoice_state
    'none'
    >>> len(purchase.invoices)
    0
