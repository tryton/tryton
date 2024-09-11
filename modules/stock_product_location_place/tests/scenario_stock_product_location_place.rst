=====================================
Stock Product Location Place Scenario
=====================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_product_location_place', create_company)

    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Get location::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])

    >>> child_loc = Location(name="Child Location")
    >>> child_loc.parent = storage_loc
    >>> child_loc.code = 'CHI'
    >>> child_loc.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.0000')
    >>> template.save()
    >>> product, = template.products

Set location places on template::

    >>> location_place = template.location_places.new()
    >>> location_place.location = storage_loc
    >>> location_place.place = "P1"
    >>> location_place = template.location_places.new()
    >>> location_place.location = child_loc
    >>> location_place.place = "C1"
    >>> template.save()

Check places on move::

    >>> move = Move(product=product)
    >>> move.from_place
    >>> move.to_place

    >>> move.from_location = storage_loc
    >>> move.from_place.rec_name
    'P1'
    >>> move.to_location = child_loc
    >>> move.to_place.rec_name
    'C1'

Set location place on product::

    >>> location_place = product.location_places.new()
    >>> location_place.location = storage_loc
    >>> location_place.place = "P2"
    >>> location_place = product.location_places.new()
    >>> location_place.location = child_loc
    >>> location_place.place = "C2"
    >>> product.save()

Check places on move::

    >>> move = Move(product=product)
    >>> move.from_place
    >>> move.to_place

    >>> move.from_location = storage_loc
    >>> move.from_place.rec_name
    'P2'
    >>> move.to_location = child_loc
    >>> move.to_place.rec_name
    'C2'
