=============================
Sale Default Methods Scenario
=============================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create a party and set their default methods::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.sale_shipment_method = 'invoice'
    >>> customer.sale_invoice_method = 'shipment'
    >>> customer.save()

Create a sale to to check default methods::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.shipment_method
    'invoice'
    >>> sale.invoice_method
    'shipment'
