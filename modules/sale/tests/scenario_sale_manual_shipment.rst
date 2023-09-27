=============================
Sale Manual Shipment Scenario
=============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('sale')

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Create company::

    >>> _ = create_company()

Create party::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.save()
    >>> product, = template.products

Sale with manual shipment method::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.shipment_method = 'manual'
    >>> sale.invoice_method = 'manual'  # no need for accounting
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> len(sale.shipments)
    0

Manually create a shipment::

    >>> sale.click('manual_shipment')
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'waiting'

Change quantity on shipment and create a new shipment::

    >>> shipment, = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.quantity = 5
    >>> shipment.save()

    >>> len(sale.shipments)
    1
    >>> sale.click('manual_shipment')
    >>> len(sale.shipments)
    2
