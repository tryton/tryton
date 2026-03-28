==================================================
Account Stock EU Excise Shipment Internal Scenario
==================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('account_stock_eu_excise')

    >>> ExciseCode = Model.get('product.eu.excise_code')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentInternal = Model.get('stock.shipment.internal')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Setup tax warehouses::

    >>> excise_code = ExciseCode(code='W200')
    >>> excise_code.save()

    >>> company_party = company.party
    >>> _ = company_party.addresses.new()
    >>> company_party.save()
    >>> address1, address2 = company_party.addresses
    >>> excise_number = company_party.identifiers.new(type='eu_excise')
    >>> excise_number.address = address1
    >>> excise_number.code = "LU00000987ABC"
    >>> excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> excise_number = company_party.identifiers.new(type='eu_excise')
    >>> excise_number.address = address2
    >>> excise_number.code = "LU00000987DEF"
    >>> excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> company_party.save()
    >>> excise_number1, excise_number2 = company_party.identifiers

    >>> warehouse1, = Location.find([('code', '=', 'WH')])
    >>> warehouse2, = warehouse1.duplicate()

    >>> warehouse1.address = address1
    >>> wh_excise_number = warehouse1.eu_excise_numbers.new()
    >>> wh_excise_number.eu_excise_number = excise_number1
    >>> warehouse1.save()

    >>> warehouse2.address = address2
    >>> wh_excise_number = warehouse2.eu_excise_numbers.new()
    >>> wh_excise_number.eu_excise_number = excise_number2
    >>> warehouse2.save()

Create product::

    >>> liter, = ProductUom.find([('name', '=', "Liter")])

    >>> template = ProductTemplate()
    >>> template.name = "Wine"
    >>> template.default_uom = liter
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20.0000')
    >>> template.eu_excise_code = excise_code
    >>> template.save()
    >>> product, = template.products

Create a internal shipment without duty suspension::

    >>> shipment = ShipmentInternal()
    >>> shipment.from_location = warehouse1.storage_location
    >>> shipment.to_location = warehouse1.output_location
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> shipment.save()
    >>> any(m.eu_excise_duty for m in shipment.moves)
    False

Change duty suspension::

    >>> shipment = ShipmentInternal()
    >>> shipment.from_location = warehouse1.storage_location
    >>> shipment.to_location = warehouse2.storage_location
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> shipment.save()
    >>> [m.eu_excise_duty for m in shipment.moves]
    ['suspension']
