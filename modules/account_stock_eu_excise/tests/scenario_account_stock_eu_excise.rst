================================
Account Stock EU Excise Scenario
================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account_stock_eu_excise')

    >>> ExciseCode = Model.get('product.eu.excise_code')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentIn = Model.get('stock.shipment.in')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Setup tax warehouse::

    >>> excise_code = ExciseCode(code='W200')
    >>> excise_code.save()

    >>> company_party = company.party
    >>> excise_number = company_party.identifiers.new(type='eu_excise')
    >>> excise_number.address, = company_party.addresses
    >>> excise_number.code = "LU00000987ABC"
    >>> excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> company_party.save()
    >>> excise_number, = company_party.identifiers

    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> warehouse.address, = company_party.addresses
    >>> wh_excise_number = warehouse.eu_excise_numbers.new()
    >>> wh_excise_number.eu_excise_number = excise_number
    >>> warehouse.save()

Create supplier::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> supplier_excise_number = supplier.identifiers.new(type='eu_excise')
    >>> supplier_excise_number.address, = supplier.addresses
    >>> supplier_excise_number.code = "LU00000987DEF"
    >>> supplier_excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> supplier.save()
    >>> supplier_excise_number, = supplier.identifiers

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

Create a shipment without duty suspension::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> assertEqual(shipment.warehouse_eu_excise_number, excise_number)
    >>> bool(shipment.has_eu_excise_goods)
    False
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = company.currency
    >>> bool(shipment.has_eu_excise_goods)
    True
    >>> shipment.save()
    >>> move, = shipment.incoming_moves
    >>> move.eu_excise_duty

Change for duty suspension::

    >>> shipment.eu_excise_types
    ('eu_excise',)
    >>> assertEqual(shipment.eu_excise_party, supplier)
    >>> shipment.eu_excise_number = supplier_excise_number
    >>> shipment.save()
    >>> move, = shipment.incoming_moves
    >>> move.eu_excise_duty
    'suspension'
