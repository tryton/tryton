============================================
Account Stock EU Excise Declaration Scenario
============================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['account_stock_eu_excise', 'production', 'product_measurements'])

    >>> Country = Model.get('country.country')
    >>> ExciseCode = Model.get('product.eu.excise_code')
    >>> ExciseTax = Model.get('account.stock.eu.excise.tax')
    >>> ExciseDeclaration = Model.get(
    ...     'account.stock.eu.excise.declaration')
    >>> ExciseDeclarationProductLine = Model.get(
    ...     'account.stock.eu.excise.declaration.product.line')
    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Production = Model.get('production')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> ShipmentOut = Model.get('stock.shipment.out')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get units::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> liter, = ProductUom.find([('name', '=', "Liter")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])


Setup tax warehouse::

    >>> excise_code = ExciseCode(code='W200')
    >>> excise_code.save()

    >>> france = Country(code='FR', name='France')
    >>> france.save()
    >>> excise_tax = ExciseTax(code='TAX')
    >>> excise_tax.quantity = 'measurement_volume'
    >>> excise_tax.uom = liter
    >>> excise_tax.country = france
    >>> excise_tax.save()

    >>> company_party = company.party
    >>> company_address, = company_party.addresses
    >>> company_address.country = france
    >>> company_address.save()
    >>> excise_number = company_party.identifiers.new(type='eu_excise')
    >>> excise_number.address = company_address
    >>> excise_number.code = "LU00000987ABC"
    >>> excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> company_party.save()
    >>> excise_number, = company_party.identifiers

    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> warehouse.address = company_address
    >>> wh_excise_number = warehouse.eu_excise_numbers.new()
    >>> wh_excise_number.eu_excise_number = excise_number
    >>> warehouse.save()

Create party::

    >>> party = Party(name="Supplier")
    >>> party.save()
    >>> party_excise_number = party.identifiers.new(type='eu_excise')
    >>> party_excise_number.address, = party.addresses
    >>> party_excise_number.code = "LU00000987DEF"
    >>> party_excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> party.save()
    >>> party_excise_number, = party.identifiers

Create product::

    >>> template = ProductTemplate()
    >>> template.name = "Wine"
    >>> template.default_uom = unit
    >>> template.volume = 2
    >>> template.volume_uom = liter
    >>> template.weight = 1.5
    >>> template.weight_uom = kg
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20.0000')
    >>> template.eu_excise_code = excise_code
    >>> _ = template.eu_excise_taxes.new(excise_tax=excise_tax)
    >>> template.save()
    >>> product, = template.products

Receive 10 products without duty suspension::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = party
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = company.currency
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Receive 5 products with duty suspension::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = party
    >>> shipment.eu_excise_number = party_excise_number
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.quantity = 5
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = company.currency
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Ship 3 products without duty suspension::

    >>> shipment = ShipmentOut()
    >>> shipment.customer = party
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 4
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('ship')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Ship 2 products with duty suspension::

    >>> shipment = ShipmentOut()
    >>> shipment.customer = party
    >>> shipment.eu_excise_number = party_excise_number
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 3
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('ship')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Use 2 product for production and get 1::

    >>> production = Production()
    >>> move = production.inputs.new()
    >>> move.product = product
    >>> move.quantity = 2
    >>> move.from_location = production.warehouse.storage_location
    >>> move.to_location = production.location
    >>> move = production.outputs.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = production.location
    >>> move.to_location = production.warehouse.storage_location
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = company.currency
    >>> production.click('wait')
    >>> production.click('assign_try')
    >>> production.click('run')
    >>> production.click('do')
    >>> production.state
    'done'

Lost 1 product::

    >>> inventory = Inventory()
    >>> inventory.location = warehouse.storage_location
    >>> inventory.empty_quantity = 'keep'
    >>> line = inventory.lines.new()
    >>> line.product = product
    >>> line.quantity = 6
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Check excise declaration in volume::

    >>> with config.set_context(
    ...         warehouse=warehouse.id,
    ...         from_date=today - dt.timedelta(days=1),
    ...         to_date=today):
    ...     declaration, = ExciseDeclaration.find(
    ...         [('eu_excise_tax', '=', excise_tax.id)])
    ...     declaration_product_lines = ExciseDeclarationProductLine.find(
    ...         [('product', '=', product.id)])

    >>> assertEqual(declaration.unit, liter)

    >>> declaration_product, = declaration.products
    >>> assertEqual(declaration_product.unit, liter)

    >>> declaration.start_quantity
    0.0
    >>> declaration.input_production
    2.0
    >>> declaration.input_duty_suspension
    10.0
    >>> declaration.input_replacement
    20.0
    >>> declaration.input_other
    0.0
    >>> declaration.input_total
    32.0
    >>> declaration.output_with_duty
    8.0
    >>> declaration.output_production
    4.0
    >>> declaration.output_duty_suspension
    6.0
    >>> declaration.output_duty_free
    0.0
    >>> declaration.output_other
    2.0
    >>> declaration.end_quantity
    12.0

    >>> assertEqual({l.date for l in declaration_product_lines}, {today})
    >>> assertEqual({l.unit for l in declaration_product_lines}, {liter})
    >>> sorted((l.quantity, l.duty) for l in declaration_product_lines)
    [(-8.0, None), (-6.0, 'suspension'), (-4.0, None), (-2.0, None), (2.0, None), (10.0, 'suspension'), (20.0, None)]

Check excise declaration product in weight::

    >>> excise_tax.quantity = 'measurement_weight'
    >>> excise_tax.uom = kg
    >>> excise_tax.save()

    >>> declaration.reload()
    >>> for l in declaration_product_lines:
    ...     l.reload()

    >>> assertEqual(declaration.unit, kg)

    >>> declaration_product, = declaration.products
    >>> assertEqual(declaration_product.unit, kg)

    >>> declaration.start_quantity
    0.0
    >>> declaration.input_production
    1.5
    >>> declaration.input_duty_suspension
    7.5
    >>> declaration.input_replacement
    15.0
    >>> declaration.input_other
    0.0
    >>> declaration.input_total
    24.0
    >>> declaration.output_with_duty
    6.0
    >>> declaration.output_production
    3.0
    >>> declaration.output_duty_suspension
    4.5
    >>> declaration.output_duty_free
    0.0
    >>> declaration.output_other
    1.5
    >>> declaration.end_quantity
    9.0

    >>> assertEqual({l.date for l in declaration_product_lines}, {today})
    >>> assertEqual({l.unit for l in declaration_product_lines}, {kg})
    >>> sorted((l.quantity, l.duty) for l in declaration_product_lines)
    [(-6.0, None), (-4.5, 'suspension'), (-3.0, None), (-1.5, None), (1.5, None), (7.5, 'suspension'), (15.0, None)]
