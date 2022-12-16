===================================
Stock Shipment Cost Weight Scenario
===================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Patch _get_shipment_cost::

    >>> from unittest.mock import patch
    >>> from trytond.modules.stock_shipment_cost.stock import ShipmentCostMixin
    >>> mock = patch.object(
    ...     ShipmentCostMixin, '_get_shipment_cost',
    ...     return_value=Decimal('8')).start()

Activate modules::

    >>> config = activate_modules('stock_shipment_cost_weight')

    >>> Carrier = Model.get('carrier')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Shipment = Model.get('stock.shipment.out')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> gram, = ProductUom.find([('name', '=', "Gram")])

    >>> template = ProductTemplate()
    >>> template.name = "Product1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.weight = 500
    >>> template.weight_uom = gram
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('10.0000')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product2"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.weight = 250
    >>> template.weight_uom = gram
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('20.0000')
    >>> product2.save()

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = "Carrier Product"
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

Create carrier::

    >>> carrier = Carrier()
    >>> carrier.party = Party(name="Carrier")
    >>> carrier.party.save()
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipment_cost_allocation_method = 'weight'
    >>> carrier.save()

Get stock locations::

    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])

Create a customer shipment::

    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> shipment.carrier = carrier
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('30')
    >>> move.currency = company.currency
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product2
    >>> move.quantity = 2
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('40')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check move costs::

    >>> sorted([
    ...         (m.cost_price, m.shipment_out_cost_price)
    ...         for m in shipment.outgoing_moves])
    [(Decimal('10.0000'), Decimal('4.0000')), (Decimal('20.0000'), Decimal('2.0000'))]
