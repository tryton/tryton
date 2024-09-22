==================================
Account Stock EU Dispatch Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> import io
    >>> import zipfile
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> intrastat_extended = globals().get('intrastat_extended', False)
    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules([
    ...     'account_stock_eu', 'incoterm',
    ...     'stock_shipment_cost', 'stock_package_shipping'])

    >>> Carrier = Model.get('carrier')
    >>> Country = Model.get('country.country')
    >>> Incoterm = Model.get('incoterm.incoterm')
    >>> IntrastatDeclaration = Model.get('account.stock.eu.intrastat.declaration')
    >>> IntrastatDeclarationLine = Model.get(
    ...     'account.stock.eu.intrastat.declaration.line')
    >>> IntrastatTransport = Model.get('account.stock.eu.intrastat.transport')
    >>> Organization = Model.get('country.organization')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> ShipmentInReturn = Model.get('stock.shipment.in.return')
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
    >>> china = Country(name="China", code='CN')
    >>> china.save()

    >>> member = europe.members.new(country=belgium)
    >>> member = europe.members.new(country=france)
    >>> europe.save()

Create currency::

    >>> eur = get_currency('EUR')
    >>> usd = get_currency('USD')

Create company in Belgium::

    >>> _ = create_company(currency=eur)
    >>> company = get_company()
    >>> company.incoterms.extend(Incoterm.find())
    >>> company.save()
    >>> company_address, = company.party.addresses
    >>> company_address.country = belgium
    >>> company_address.subdivision = liege
    >>> company_address.save()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.intrastat_extended = intrastat_extended
    >>> fiscalyear.save()

Create suppliers::

    >>> customer_be = Party(name="Customer BE")
    >>> address, = customer_be.addresses
    >>> address.country = belgium
    >>> customer_be.save()

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

    >>> customer_us = Party(name="Customer US")
    >>> address, = customer_us.addresses
    >>> address.country = united_state
    >>> customer_us.save()

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
    >>> template.country_of_origin = china
    >>> template.save()
    >>> product, = template.products

Create carriers::

    >>> carrier_template = ProductTemplate(name="Carrier Product")
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.list_price = Decimal('5')
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

    >>> road_transport, = IntrastatTransport.find([('name', '=', "Road transport")])
    >>> carrier = Carrier()
    >>> party = Party(name="Carrier")
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipment_cost_allocation_method = 'cost'
    >>> carrier.intrastat_transport = road_transport
    >>> carrier.save()

Get stock locations::

    >>> warehouse_loc, = StockLocation.find([('code', '=', 'WH')])
    >>> warehouse_loc.address = company_address
    >>> warehouse_loc.save()

Send products to Belgium::

    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer_be
    >>> shipment.carrier = carrier
    >>> move = shipment.outgoing_moves.new()
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.unit_price = Decimal('100.0000')
    >>> move.currency = eur
    >>> shipment.click('wait')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

    >>> move, = shipment.outgoing_moves
    >>> move.intrastat_type

Send products to particular to France::

    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer_fr
    >>> shipment.carrier = carrier
    >>> shipment.incoterm, = Incoterm.find([
    ...         ('code', '=', 'FCA'), ('version', '=', '2020')])
    >>> shipment.incoterm_location = shipment.delivery_address
    >>> move = shipment.outgoing_moves.new()
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.product = product
    >>> move.quantity = 20
    >>> move.unit_price = Decimal('90.0000')
    >>> move.currency = eur
    >>> shipment.click('wait')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

    >>> move, = shipment.outgoing_moves
    >>> move.intrastat_type
    'dispatch'
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
    '12'
    >>> move.intrastat_additional_unit
    20.0
    >>> move.intrastat_country_of_origin.code
    'CN'
    >>> move.intrastat_vat
    >>> assertEqual(move.intrastat_declaration.month, today.replace(day=1))


Send products to US::

    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer_us
    >>> shipment.carrier = carrier
    >>> move = shipment.outgoing_moves.new()
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.product = product
    >>> move.quantity = 30
    >>> move.unit_price = Decimal('120.0000')
    >>> move.currency = usd
    >>> shipment.click('wait')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.inventory_moves
    >>> move.intrastat_type

    >>> move, = shipment.outgoing_moves
    >>> move.intrastat_type

Send returned products to France::

    >>> shipment = ShipmentInReturn()
    >>> shipment.supplier = supplier_fr
    >>> shipment.from_location = warehouse_loc.storage_location
    >>> shipment.carrier = carrier
    >>> shipment.incoterm, = Incoterm.find([
    ...         ('code', '=', 'EXW'), ('version', '=', '2020')])
    >>> move = shipment.moves.new()
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> move.product = product
    >>> move.quantity = 5
    >>> move.unit_price = Decimal('150.0000')
    >>> move.currency = eur
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> move, = shipment.moves
    >>> move.intrastat_type
    'dispatch'
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
    >>> move.intrastat_country_of_origin.code
    'CN'
    >>> move.intrastat_vat.code
    'FR40303265045'
    >>> assertEqual(move.intrastat_declaration.month, today.replace(day=1))

Check declaration::

    >>> declaration, = IntrastatDeclaration.find([])
    >>> declaration.country.code
    'BE'
    >>> assertEqual(declaration.month, today.replace(day=1))
    >>> declaration.state
    'opened'

    >>> with config.set_context(declaration=declaration.id):
    ...     _, declaration_line = IntrastatDeclarationLine.find([])
    >>> declaration_line.type
    'dispatch'
    >>> declaration_line.country.code
    'FR'
    >>> declaration_line.subdivision.intrastat_code
    '2'
    >>> declaration_line.tariff_code.code
    '9403 10 51'
    >>> declaration_line.weight
    15.0
    >>> declaration_line.value
    Decimal('750.00')
    >>> declaration_line.transaction.code
    '21'
    >>> declaration_line.additional_unit
    5.0
    >>> declaration_line.country_of_origin.code
    'CN'
    >>> declaration_line.vat.code
    'FR40303265045'
    >>> assertEqual(declaration_line.transport, road_transport)
    >>> declaration_line.incoterm.code
    'EXW'

Export declaration::

    >>> _ = declaration.click('export')
    >>> export = Wizard('account.stock.eu.intrastat.declaration.export', [declaration])
    >>> export.form.filename.endswith('.csv')
    True
    >>> assertEqual(
    ...     export.form.file,
    ...     b'29;FR;12;2;9403 10 51;60.0;20.0;1800.00;3;FCA;CN;\r\n'
    ...     b'29;FR;21;2;9403 10 51;15.0;5.0;750.00;3;EXW;CN;FR40303265045\r\n'
    ...     if intrastat_extended else
    ...     b'29;FR;12;2;9403 10 51;60.0;20.0;1800.00;CN;\r\n'
    ...     b'29;FR;21;2;9403 10 51;15.0;5.0;750.00;CN;FR40303265045\r\n')
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
    ['dispatch-0.csv']
    >>> assertEqual(
    ...     zip.open('dispatch-0.csv').read(),
    ...     b'FR;2;FCA;12;3;;9403 10 51;CN;;60.0;20.0;1800.00;1800.00;\r\n'
    ...     b'FR;2;EXW;21;3;;9403 10 51;CN;;15.0;5.0;750.00;750.00;FR40303265045\r\n'
    ...     if intrastat_extended else
    ...     b'FR;2;;12;;;9403 10 51;CN;;60.0;20.0;1800.00;1800.00;\r\n'
    ...     b'FR;2;;21;;;9403 10 51;CN;;15.0;5.0;750.00;750.00;FR40303265045\r\n')

Export declaration as fallback::

    >>> belgium.code = 'XX'
    >>> belgium.save()

    >>> _ = declaration.click('export')
    >>> export = Wizard('account.stock.eu.intrastat.declaration.export', [declaration])
    >>> export.form.filename.endswith('.csv')
    True
    >>> assertEqual(
    ...     export.form.file,
    ...     b'dispatch,FR,2,9403 10 51,60.0,1800.00,12,20.0,CN,,3,FCA\r\n'
    ...     b'dispatch,FR,2,9403 10 51,15.0,750.00,21,5.0,CN,FR40303265045,3,EXW\r\n'
    ...     if intrastat_extended else
    ...     b'dispatch,FR,2,9403 10 51,60.0,1800.00,12,20.0,CN,\r\n'
    ...     b'dispatch,FR,2,9403 10 51,15.0,750.00,21,5.0,CN,FR40303265045\r\n')
