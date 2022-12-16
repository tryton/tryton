=======================
Purchase Empty Scenario
=======================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart

Install purchase::

    >>> config = activate_modules('purchase')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)

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
    u'quotation'
    >>> purchase.untaxed_amount
    Decimal('0')
    >>> purchase.tax_amount
    Decimal('0')
    >>> purchase.total_amount
    Decimal('0')
    >>> purchase.click('confirm')
    >>> purchase.state
    u'confirmed'
    >>> purchase.click('process')
    >>> purchase.state
    u'done'
    >>> purchase.shipment_state
    u'none'
    >>> len(purchase.moves)
    0
    >>> len(purchase.shipment_returns)
    0
    >>> purchase.invoice_state
    u'none'
    >>> len(purchase.invoices)
    0
