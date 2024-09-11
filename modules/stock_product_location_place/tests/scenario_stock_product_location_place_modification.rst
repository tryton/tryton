==================================================
Stock Product Location Place Modification Scenario
==================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_product_location_place', create_company)

    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Get location::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create products with different location places::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.0000')
    >>> _ = template.products.new()
    >>> template.save()
    >>> product1, product2 = template.products

    >>> location_place1 = product1.location_places.new()
    >>> location_place1.location = storage_loc
    >>> location_place1.place = "P1"
    >>> product1.save()

    >>> location_place2 = product2.location_places.new()
    >>> location_place2.location = storage_loc
    >>> location_place2.place = "P2"
    >>> product2.save()

Create a stock move::

    >>> move = Move(product=product1)
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.quantity = 1
    >>> move.unit_price = Decimal(10)
    >>> move.currency = get_currency()
    >>> move.save()

    >>> move.to_place.rec_name
    'P1'

Change product::

    >>> move.product = product2
    >>> move.save()

    >>> move.to_place.rec_name
    'P2'
