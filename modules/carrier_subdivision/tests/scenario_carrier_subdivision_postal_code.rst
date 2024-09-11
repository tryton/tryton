========================================
Carrier Subdivision Postal Code Scenario
========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['carrier_subdivision', 'sale_shipment_cost'], create_company)

Create customers::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> address, = customer.addresses
    >>> address.postal_code = '08080'
    >>> customer.save()
    >>> other_customer = Party(name='Other Customer')
    >>> address, = other_customer.addresses
    >>> address.postal_code = '25175'
    >>> other_customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

Create carriers::

    >>> Carrier = Model.get('carrier')
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()
    >>> local_carrier = Carrier()
    >>> party = Party(name='Local Carrier')
    >>> party.save()
    >>> local_carrier.party = party
    >>> local_carrier.carrier_product = carrier_product
    >>> local_carrier.save()

Create postal code selection for each carrier::

    >>> CarrierSelection = Model.get('carrier.selection')
    >>> csc = CarrierSelection()
    >>> csc.carrier = local_carrier
    >>> csc.to_postal_code = '25'
    >>> csc.sequence = 10
    >>> csc.save()
    >>> csc = CarrierSelection()
    >>> csc.carrier = carrier
    >>> csc.sequence = 20
    >>> csc.save()

Test right carrier is used on sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> assertEqual(sale.carrier, carrier)
    >>> sale.carrier = None
    >>> sale.party = other_customer
    >>> assertEqual(sale.carrier, local_carrier)
