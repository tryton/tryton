========================================================
Stock Shipping Point with Shipment Measurements Scenario
========================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_shipping_point', 'stock_shipment_measurements'],
    ...     create_company)

    >>> Party = Model.get('party.party')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Shipment = Model.get('stock.shipment.out')
    >>> ShippingPoint = Model.get('stock.shipping.point')
    >>> ShippingPointSelection = Model.get('stock.shipping.point.selection')

Get currency::

    >>> currency = get_currency()

Create a customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create a product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> gr, = ProductUom.find([('name', '=', 'Gram')])
    >>> liter, = ProductUom.find([('name', '=', 'Liter')])
    >>> cm3, = ProductUom.find([('name', '=', 'Cubic centimeter')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.weight = 500
    >>> template.weight_uom = gr
    >>> template.volume = 100
    >>> template.volume_uom = cm3
    >>> template.save()
    >>> product, = template.products

Create some shipping point::

    >>> shipping_point1 = ShippingPoint(name="Point 1")
    >>> shipping_point1.save()
    >>> shipping_point2 = ShippingPoint(name="Point 2")
    >>> shipping_point2.save()

Setup selections::

    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point2,
    ...     min_weight=1, max_weight=10, weight_uom=kg,
    ...     min_volume=1, max_volume=100, volume_uom=liter).save()
    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point1,
    ...     min_weight=.2, max_weight=1, weight_uom=kg,
    ...     min_volume=.01, max_volume=1, volume_uom=liter).save()

Create a customer shipment::

    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.unit_price = Decimal('42.0000')
    >>> move.currency = currency
    >>> shipment.save()
    >>> shipment.state
    'draft'
    >>> shipment.shipping_point

Wait the customer shipment::

    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> assertEqual(shipment.shipping_point, shipping_point1)
