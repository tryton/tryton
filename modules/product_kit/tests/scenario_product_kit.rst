====================
Product Kit Scenario
====================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate product_kit and stock::

    >>> config = activate_modules(['product_kit', 'stock'])

Create company::

    >>> _ = create_company()

Create products::

    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> meter, = Uom.find([('name', '=', "Meter")])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('10.0000')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 2"
    >>> template.default_uom = meter
    >>> template.type = 'goods'
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('20.0000')
    >>> product2.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 3"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product3, = template.products
    >>> product3.cost_price = Decimal('1.0000')
    >>> product3.save()

    >>> template = ProductTemplate()
    >>> template.name = "Service"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.save()
    >>> service, = template.products
    >>> service.cost_price = Decimal('5.0000')
    >>> service.save()

Create composed product::

    >>> template = ProductTemplate()
    >>> template.name = "Composed Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> composed_product, = template.products
    >>> composed_product.cost_price = Decimal('10.0000')

    >>> component = composed_product.components.new()
    >>> component.product = product1
    >>> component.quantity = 2
    >>> component = composed_product.components.new()
    >>> component.product = service
    >>> component.quantity = 1
    >>> composed_product.save()

    >>> composed_product.cost_price
    Decimal('10.0000')

Create a kit::

    >>> template = ProductTemplate()
    >>> template.name = "Kit"
    >>> template.default_uom = unit
    >>> template.type = 'kit'
    >>> template.save()
    >>> kit, = template.products

    >>> component = template.components.new()
    >>> component.product = product1
    >>> component.quantity = 1
    >>> component = template.components.new()
    >>> component.product = product2
    >>> component.quantity = 2
    >>> component = template.components.new()
    >>> component.product = product3
    >>> component.quantity = 1
    >>> component.fixed = True
    >>> template.save()

    >>> kit.cost_price
    Decimal('51.0000')

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Fill stock with some components::

    >>> StockMove = Model.get('stock.move')
    >>> moves = []

    >>> move = StockMove()
    >>> move.product = product1
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('10')
    >>> moves.append(move)

    >>> move = StockMove()
    >>> move.product = product2
    >>> move.quantity = 15
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('20')
    >>> moves.append(move)

    >>> move = StockMove()
    >>> move.product = product3
    >>> move.quantity = 20
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('1')
    >>> moves.append(move)

    >>> StockMove.click(moves, 'do')

Check kit quantity::

    >>> with config.set_context(locations=[storage_loc.id]):
    ...     kit = Product(kit.id)
    >>> kit.quantity
    7.0
