============================
Carrier Subdivision Scenario
============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules(['carrier_subdivision', 'sale_shipment_cost'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create subdivisions::

    >>> Country = Model.get('country.country')
    >>> Subdivision = Model.get('country.subdivision')
    >>> spain = Country(name='Spain', code='ES')
    >>> spain.save()
    >>> catalonia = Subdivision()
    >>> catalonia.code = 'ES-CAT'
    >>> catalonia.name = 'Catalonia'
    >>> catalonia.country = spain
    >>> catalonia.type = 'autonomous community'
    >>> catalonia.save()
    >>> barcelona = Subdivision()
    >>> barcelona.code = 'ES-BCN'
    >>> barcelona.name = 'Barcelona'
    >>> barcelona.country = spain
    >>> barcelona.type = 'province'
    >>> barcelona.parent = catalonia
    >>> barcelona.save()
    >>> madrid = Subdivision()
    >>> madrid.code = 'ES-MAD'
    >>> madrid.name = 'Madrid'
    >>> madrid.country = spain
    >>> madrid.type = 'province'
    >>> madrid.save()

Create customers::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> address, = customer.addresses
    >>> address.country = spain
    >>> address.subdivision = madrid
    >>> customer.save()
    >>> other_customer = Party(name='Other Customer')
    >>> address, = other_customer.addresses
    >>> address.country = spain
    >>> address.subdivision = barcelona
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
    >>> catalan_carrier = Carrier()
    >>> party = Party(name='Catalan Carrier')
    >>> party.save()
    >>> catalan_carrier.party = party
    >>> catalan_carrier.carrier_product = carrier_product
    >>> catalan_carrier.save()

Set subdivision for each carrier::

    >>> CarrierSelection = Model.get('carrier.selection')
    >>> csc = CarrierSelection()
    >>> csc.carrier = catalan_carrier
    >>> csc.to_country = spain
    >>> csc.to_subdivision = catalonia
    >>> csc.sequence = 10
    >>> csc.save()
    >>> csc = CarrierSelection()
    >>> csc.carrier = carrier
    >>> csc.to_country = spain
    >>> csc.sequence = 20
    >>> csc.save()

Test right carrier is used on sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier == carrier
    True
    >>> sale.carrier = None
    >>> sale.party = other_customer
    >>> sale.carrier == catalan_carrier
    True
