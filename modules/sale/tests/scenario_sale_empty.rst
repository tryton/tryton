===================
Sale Empty Scenario
===================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart

Activate modules::

    >>> config = activate_modules('sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create empty sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.click('quote')
    >>> sale.state
    'quotation'
    >>> sale.untaxed_amount
    Decimal('0')
    >>> sale.tax_amount
    Decimal('0')
    >>> sale.total_amount
    Decimal('0')
    >>> sale.click('confirm')
    >>> sale.state
    'done'
    >>> sale.shipment_state
    'none'
    >>> len(sale.shipments)
    0
    >>> len(sale.shipment_returns)
    0
    >>> sale.invoice_state
    'none'
    >>> len(sale.invoices)
    0
