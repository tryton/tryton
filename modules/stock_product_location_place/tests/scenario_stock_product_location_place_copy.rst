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
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Get location::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create product with location places::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.0000')
    >>> location_place = template.location_places.new()
    >>> location_place.location = storage_loc
    >>> location_place.place = "P1"
    >>> template.save()
    >>> product, = template.products
    >>> location_place = product.location_places.new()
    >>> location_place.location = storage_loc
    >>> location_place.place = "P2"
    >>> product.save()

Location places are copied when copying template::

    >>> template_copy, = template.duplicate()
    >>> product_copy, = template_copy.products
    >>> len(template_copy.location_places)
    2
    >>> len(product_copy.location_places)
    1
