=========================================================
Stock Shipping Point with Product Classification Scenario
=========================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_shipping_point', 'product_classification_taxonomic'],
    ...     create_company)

    >>> Party = Model.get('party.party')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Shipment = Model.get('stock.shipment.out')
    >>> ShippingPoint = Model.get('stock.shipping.point')
    >>> ShippingPointSelection = Model.get('stock.shipping.point.selection')
    >>> Taxon = Model.get('product.taxon')
    >>> Cultivar = Model.get('product.cultivar')

Get currency::

    >>> currency = get_currency()

Create a customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create classifications::

    >>> taxon = Taxon(name="Taxon")
    >>> taxon.save()
    >>> taxon_child = Taxon(name="Taxon Child", parent=taxon)
    >>> taxon_child.save()

    >>> cultivar = Cultivar(name="Cultivar", taxon=taxon_child)
    >>> cultivar.save()

Create a product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
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
    ...     contains_product_classification=taxon).save()
    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point1,
    ...     contains_product_classification=cultivar).save()

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

Wait the customer shipment with taxon::

    >>> template.classification = taxon_child
    >>> template.save()

    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> assertEqual(shipment.shipping_point, shipping_point2)

Reset to draft::

    >>> shipment.click('draft')
    >>> shipment.state
    'draft'

Wait the customer shipment with cultivar::

    >>> template.classification = cultivar
    >>> template.save()

    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> assertEqual(shipment.shipping_point, shipping_point1)
