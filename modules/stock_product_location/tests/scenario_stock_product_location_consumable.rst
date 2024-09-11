==========================================
Stock Product Location Consumable Scenario
==========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_product_location', create_company)

    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> UoM = Model.get('product.uom')

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create consumable location::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])

    >>> consumable_loc = Location(name="Consumable")
    >>> consumable_loc.parent = warehouse_loc
    >>> consumable_loc.save()

Create consumable product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Consumable")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.consumable = True
    >>> product_location = template.locations.new()
    >>> product_location.warehouse = warehouse_loc
    >>> product_location.location = consumable_loc
    >>> template.save()
    >>> product, = template.products

Ship consumable product to customer::

    >>> shipment = ShipmentOut(customer=customer)
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.unit_price = Decimal(0)
    >>> move.currency = shipment.company.currency
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'

Assign the shipment::

    >>> shipment_assign = shipment.click('assign_wizard')
    >>> shipment.state
    'assigned'

Check assigned from consumable location::

    >>> move, = shipment.inventory_moves
    >>> assertEqual(move.from_location, consumable_loc)
