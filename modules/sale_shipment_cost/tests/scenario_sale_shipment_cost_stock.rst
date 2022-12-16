=================================
Sale Shipment Cost Stock Scenario
=================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules([
    ...         'sale_shipment_cost',
    ...         'sale',
    ...         'stock_shipment_cost',
    ...         ])

    >>> Carrier = Model.get('carrier')
    >>> CarrierSelection = Model.get('carrier.selection')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')
    >>> ShipmentOut = Model.get('stock.shipment.out')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('2')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('5')
    >>> carrier_product.save()

Create carrier::

    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Use it as the default carrier::

    >>> csc = CarrierSelection(carrier=carrier)
    >>> csc.save()


Sell product with no shipment cost::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.shipment_cost_method = None
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> len(sale.lines)
    1
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

    >>> shipment, = sale.shipments
    >>> shipment.cost_used
    Decimal('5.0000')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> move, = shipment.outgoing_moves
    >>> move.shipment_out_cost_price
    Decimal('5.0000')

Sell product with cost on shipment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.shipment_cost_method = 'shipment'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> len(sale.lines)
    2
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

    >>> shipment, = sale.shipments
    >>> shipment.cost_used
    Decimal('5.0000')
    >>> shipment.cost_sale_used
    Decimal('2.0000')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> move, = shipment.outgoing_moves
    >>> move.shipment_out_cost_price
    Decimal('3.0000')

Sell product with cost on order::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.shipment_cost_method = 'order'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> len(sale.lines)
    2
    >>> sale.click('draft')
    >>> sale.lines[-1].unit_price = Decimal('3.0000')
    >>> sale.click('quote')
    >>> sale.lines[-1].unit_price
    Decimal('3.0000')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

    >>> shipment, = sale.shipments
    >>> shipment.cost_used
    Decimal('5.0000')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> move, = shipment.outgoing_moves
    >>> move.shipment_out_cost_price
    Decimal('2.0000')
