=================================
Account Stock EU Arrival Scenario
=================================

Imports::

    >>> import datetime as dt
    >>> import io
    >>> import zipfile
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_stock_eu')

    >>> Country = Model.get('country.country')
    >>> IntrastatDeclaration = Model.get('account.stock.eu.intrastat.declaration')
    >>> IntrastatDeclarationLine = Model.get(
    ...     'account.stock.eu.intrastat.declaration.line')
    >>> Organization = Model.get('country.organization')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> ShipmentOutReturn = Model.get('stock.shipment.out.return')
    >>> StockLocation = Model.get('stock.location')
    >>> TariffCode = Model.get('customs.tariff.code')

Create countries::

    >>> europe, = Organization.find([('code', '=', 'EU')])
    >>> belgium = Country(name="Belgium", code='BE')
    >>> subdivision = belgium.subdivisions.new(
    ...     name="Flemish Region", intrastat_code='1', type='region')
    >>> subdivision = belgium.subdivisions.new(
    ...     name="Walloon Region", intrastat_code='2', type='region')
    >>> belgium.save()
    >>> flemish, walloon = belgium.subdivisions
    >>> subdivision = belgium.subdivisions.new(
    ...     name="Liège", type='province', parent=walloon)
    >>> belgium.save()
    >>> liege, = [s for s in belgium.subdivisions if s.parent == walloon]
    >>> france = Country(name="France", code='FR')
    >>> france.save()
    >>> united_state = Country(name="United State", code='US')
    >>> united_state.save()

    >>> member = europe.members.new(country=belgium)
    >>> member = europe.members.new(country=france)
    >>> europe.save()

Create currency::

    >>> eur = get_currency('EUR')
    >>> usd = get_currency('USD')

Create company in Belgium::

    >>> _ = create_company(currency=eur)
    >>> company = get_company()
    >>> company_address, = company.party.addresses
    >>> company_address.country = belgium
    >>> company_address.subdivision = liege
    >>> company_address.save()

Create suppliers::

    >>> supplier_be = Party(name="Supplier BE")
    >>> address, = supplier_be.addresses
    >>> address.country = belgium
    >>> identifier = supplier_be.identifiers.new(type='eu_vat')
    >>> identifier.code = "BE0428759497"
    >>> supplier_be.save()

    >>> supplier_fr = Party(name="Supplier FR")
    >>> address, = supplier_fr.addresses
    >>> address.country = france
    >>> identifier = supplier_fr.identifiers.new(type='eu_vat')
    >>> identifier.code = "FR40303265045"
    >>> supplier_fr.save()

    >>> customer_fr = Party(name="Customer FR")
    >>> address, = customer_fr.addresses
    >>> address.country = france
    >>> customer_fr.save()

    >>> supplier_us = Party(name="Supplier US")
    >>> address, = supplier_us.addresses
    >>> address.country = united_state
    >>> supplier_us.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])

    >>> tariff_code = TariffCode(code="9403 10 51")
    >>> tariff_code.description = "Desks"
    >>> tariff_code.intrastat_uom = unit
    >>> tariff_code.save()

    >>> template = ProductTemplate(name="Desk")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.cost_price = Decimal('100.0000')
    >>> _ = template.tariff_codes.new(tariff_code=tariff_code)
    >>> template.weight = 3
    >>> template.weight_uom = kg
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> warehouse_loc, = StockLocation.find([('code', '=', 'WH')])
    >>> warehouse_loc.address = company_address
    >>> warehouse_loc.save()

Receive products from Belgium::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier_be
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.unit_price = Decimal('100.0000')
    >>> move.currency = eur
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.incoming_moves
    >>> move.intrastat_type

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

Receive products from France::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier_fr
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.product = product
    >>> move.quantity = 20
    >>> move.unit_price = Decimal('90.0000')
    >>> move.currency = eur
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.incoming_moves
    >>> move.intrastat_type
    'arrival'
    >>> move.intrastat_warehouse_country.code
    'BE'
    >>> move.intrastat_country.code
    'FR'
    >>> move.intrastat_subdivision.intrastat_code
    '2'
    >>> move.intrastat_tariff_code.code
    '9403 10 51'
    >>> move.intrastat_value
    Decimal('1800.00')
    >>> move.intrastat_transaction.code
    '11'
    >>> move.intrastat_additional_unit
    20.0
    >>> move.intrastat_country_of_origin
    >>> move.intrastat_vat
    >>> assertEqual(move.intrastat_declaration.month, today.replace(day=1))

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

Receive products from US::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier_us
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.product = product
    >>> move.quantity = 30
    >>> move.unit_price = Decimal('120.0000')
    >>> move.currency = usd
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.incoming_moves
    >>> move.intrastat_type

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

Receive returned products from France::

    >>> shipment = ShipmentOutReturn()
    >>> shipment.customer = customer_fr
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = shipment.customer_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.product = product
    >>> move.quantity = 5
    >>> move.unit_price = Decimal('150.0000')
    >>> move.currency = eur
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.incoming_moves
    >>> move.intrastat_type
    'arrival'
    >>> move.intrastat_warehouse_country.code
    'BE'
    >>> move.intrastat_country.code
    'FR'
    >>> move.intrastat_subdivision.intrastat_code
    '2'
    >>> move.intrastat_tariff_code.code
    '9403 10 51'
    >>> move.intrastat_value
    Decimal('750.00')
    >>> move.intrastat_transaction.code
    '21'
    >>> move.intrastat_additional_unit
    5.0
    >>> move.intrastat_country_of_origin
    >>> move.intrastat_vat
    >>> assertEqual(move.intrastat_declaration.month, today.replace(day=1))

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

Check declaration::

    >>> declaration, = IntrastatDeclaration.find([])
    >>> declaration.country.code
    'BE'
    >>> assertEqual(declaration.month, today.replace(day=1))
    >>> declaration.state
    'opened'
    >>> bool(declaration.extended)
    False

    >>> with config.set_context(declaration=declaration.id):
    ...     declaration_line, _ = IntrastatDeclarationLine.find([])
    >>> declaration_line.type
    'arrival'
    >>> declaration_line.country.code
    'FR'
    >>> declaration_line.subdivision.intrastat_code
    '2'
    >>> declaration_line.tariff_code.code
    '9403 10 51'
    >>> declaration_line.weight
    60.0
    >>> declaration_line.value
    Decimal('1800.00')
    >>> declaration_line.transaction.code
    '11'
    >>> declaration_line.additional_unit
    20.0
    >>> declaration_line.country_of_origin
    >>> declaration_line.vat

Export declaration::

    >>> _ = declaration.click('export')
    >>> export = Wizard('account.stock.eu.intrastat.declaration.export', [declaration])
    >>> export.form.file
    b'19;FR;11;2;9403 10 51;60.0;20.0;1800.00;;\r\n19;FR;21;2;9403 10 51;15.0;5.0;750.00;;\r\n'
    >>> export.form.filename.endswith('.csv')
    True
    >>> declaration.state
    'closed'

Export declaration as Spain::

    >>> belgium.code = 'ES'
    >>> belgium.save()

    >>> _ = declaration.click('export')
    >>> export = Wizard('account.stock.eu.intrastat.declaration.export', [declaration])
    >>> export.form.filename.endswith('.zip')
    True
    >>> zip = zipfile.ZipFile(io.BytesIO(export.form.file))
    >>> zip.namelist()
    ['arrival-0.csv']
    >>> zip.open('arrival-0.csv').read()
    b'FR;2;;11;;;9403 10 51;;;60.0;20.0;1800.00;1800.00;\r\nFR;2;;21;;;9403 10 51;;;15.0;5.0;750.00;750.00;\r\n'

Export declaration as fallback::

    >>> belgium.code = 'XX'
    >>> belgium.save()

    >>> _ = declaration.click('export')
    >>> export = Wizard('account.stock.eu.intrastat.declaration.export', [declaration])
    >>> export.form.file
    b'arrival,FR,2,9403 10 51,60.0,1800.00,11,20.0,,\r\narrival,FR,2,9403 10 51,15.0,750.00,21,5.0,,\r\n'
    >>> export.form.filename.endswith('.csv')
    True
