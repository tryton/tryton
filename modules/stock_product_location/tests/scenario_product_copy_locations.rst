=============================
Product Copy Locaton Scenario
=============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('stock_product_location')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create new location::

    >>> Location = Model.get('stock.location')
    >>> child_loc = Location()
    >>> child_loc.name = 'Child Location'
    >>> child_loc.parent = storage_loc
    >>> child_loc.code = 'CHI'
    >>> child_loc.save()

Create a product with suppliers::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template_location = template.locations.new()
    >>> template_location.warehouse = warehouse_loc
    >>> template_location.location = child_loc
    >>> template.save()
    >>> product, = template.products
    >>> product_location = product.locations.new()
    >>> product_location.warehouse = warehouse_loc
    >>> product_location.location = child_loc
    >>> product_location.template == template
    True
    >>> product.save()

Location is copied when copying the template::

    >>> template_copy, = template.duplicate()
    >>> product_copy, = template_copy.products
    >>> len(template_copy.locations)
    2
    >>> len(product_copy.locations)
    1
