===============================
Purchase Shipment Cost Scenario
===============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('purchase_shipment_cost')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.list_price = Decimal('5')
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('3')
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

Create carrier::

    >>> Carrier = Model.get('carrier')
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Receive a single product line::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> Location = Model.get('stock.location')
    >>> supplier_location, = Location.find([
    ...         ('code', '=', 'SUP'),
    ...         ])
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move = Move()
    >>> shipment.incoming_moves.append(move)
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 50
    >>> move.unit_price = Decimal('8')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> move, = shipment.incoming_moves
    >>> move.unit_price
    Decimal('8.0600')

Receive many product lines::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> for quantity in (1, 3, 5):
    ...     move = Move()
    ...     shipment.incoming_moves.append(move)
    ...     move.from_location = supplier_location
    ...     move.to_location = shipment.warehouse.input_location
    ...     move.product = product
    ...     move.quantity = quantity
    ...     move.unit_price = Decimal('8')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> [move.unit_price for move in shipment.incoming_moves] == \
    ...     [Decimal('8.3333'), Decimal('8.3333'), Decimal('8.3334')]
    True

Receive a two lines with no cost::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 75
    >>> move.unit_price = Decimal('0.0')
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 25
    >>> move.unit_price = Decimal('0.0')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> tuple(m.unit_price for m in shipment.incoming_moves)
    (Decimal('0.0600'), Decimal('0.0200'))
