=============================
Stock Shipping Point Scenario
=============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_shipping_point', create_company)

    >>> Country = Model.get('country.country')
    >>> Party = Model.get('party.party')
    >>> Product = Model.get('product.product')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Shipment = Model.get('stock.shipment.out')
    >>> ShippingPoint = Model.get('stock.shipping.point')
    >>> ShippingPointSelection = Model.get('stock.shipping.point.selection')

Get currency::

    >>> currency = get_currency()

Create countries::

    >>> belgium = Country(code="BE", name="Belgium")
    >>> belgium.save()
    >>> france = Country(code="FR", name="France")
    >>> france.save()

Create a customer::

    >>> customer = Party(name='Customer')
    >>> address, = customer.addresses
    >>> address.country = belgium
    >>> customer.save()

Create product categories::

    >>> category1 = ProductCategory(name="Category 1")
    >>> category1.save()
    >>> category1_child = ProductCategory(name="Child 1", parent=category1)
    >>> category1_child.save()
    >>> category2 = ProductCategory(name="Category 2")
    >>> category2.save()

Create a product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.categories.append(category1_child)
    >>> template.save()
    >>> product, = template.products

Create some shipping point::

    >>> shipping_point1 = ShippingPoint(name="Point 1")
    >>> shipping_point1.save()
    >>> shipping_point2 = ShippingPoint(name="Point 2")
    >>> shipping_point2.save()

Setup selections::

    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point1,
    ...     delivery_country=belgium).save()
    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point2,
    ...     delivery_country=france).save()
    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point1,
    ...     contains_product_categories=[ProductCategory(category1.id)]).save()
    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point2,
    ...     contains_product_categories=[ProductCategory(category2.id)]).save()
    >>> ShippingPointSelection(
    ...     shipping_point=shipping_point1,
    ...     delivery_country=belgium,
    ...     contains_product_categories=[ProductCategory(category1.id)]).save()

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
