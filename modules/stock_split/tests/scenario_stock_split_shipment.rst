====================
Stock Split Shipment
====================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('stock_split')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create shipment with 2 lines::

    >>> Shipment = Model.get('stock.shipment.out')
    >>> Move = Model.get('stock.move')

    >>> shipment1 = Shipment()
    >>> shipment1.customer = customer

    >>> for i in range(2):
    ...     move = shipment1.outgoing_moves.new()
    ...     move.product = product
    ...     move.uom = unit
    ...     move.quantity = i
    ...     move.from_location = output_loc
    ...     move.to_location = customer_loc
    ...     move.unit_price = Decimal(1)

    >>> shipment1.save()
    >>> move1, move2 = shipment1.outgoing_moves

Set to waiting and go back to draft to get inventory moves::

    >>> shipment1.click('wait')
    >>> shipment1.click('draft')
    >>> len(shipment1.inventory_moves)
    2

Split shipment::

    >>> split_shipment = Wizard('stock.shipment.split', [shipment1])
    >>> len(split_shipment.form.domain_moves)
    2
    >>> split_shipment.form.moves.append(Move(move2.id))
    >>> split_shipment.execute('split')

    >>> shipment2, = Shipment.find([('id', '!=', shipment1.id)])

    >>> move, = shipment1.outgoing_moves
    >>> move.id == move1.id
    True
    >>> len(shipment1.inventory_moves)
    0

    >>> move, = shipment2.outgoing_moves
    >>> move.id == move2.id
    True
