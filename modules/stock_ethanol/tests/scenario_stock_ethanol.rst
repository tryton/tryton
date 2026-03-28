======================
Stock Ethanol Scenario
======================

Imports::

    >>> from decimal import Decimal
    >>> from unittest.mock import patch

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.stock.move import Move
    >>> from trytond.tests.tools import activate_modules

Patch on_change_with_assignation_required::

    >>> _ = patch.object(
    ...     Move, 'on_change_with_assignation_required',
    ...     return_value=False).start()

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_ethanol', 'product_measurements'])

    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> Uom = Model.get('product.uom')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> warehouse_loc, = Location.find([('type', '=', 'warehouse')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> lost_found_loc, = Location.find([('type', '=', 'lost_found')])

Create products::

    >>> liter, = Uom.find([('name', '=', "Liter")])
    >>> unit, = Uom.find([('name', '=', "Unit")])
    >>> cubic_meter, = Uom.find([('name', '=', "Cubic meter")])

    >>> template = ProductTemplate()
    >>> template.name = "Alcohol"
    >>> template.default_uom = liter
    >>> template.type = 'goods'
    >>> template.contain_ethanol = True
    >>> template.ethanol_by_volume = 0.5
    >>> template.save()
    >>> alcohol, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Cork"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.contain_ethanol = False
    >>> template.save()
    >>> cork, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Bottle"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.volume = 0.5
    >>> template.volume_uom = liter
    >>> template.contain_ethanol = True
    >>> template.ethanol_by_volume = 0.1
    >>> template.save()
    >>> bottle, = template.products

Receive alcohol with volume::

    >>> move = Move()
    >>> move.product = alcohol
    >>> move.quantity = 10
    >>> move.from_location = lost_found_loc
    >>> move.to_location = storage_loc
    >>> move.save()
    >>> move.click('do')

    >>> move.ethanol_volume
    5.0

Receive cork::

    >>> move = Move()
    >>> move.product = cork
    >>> move.quantity = 100
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('1.00')
    >>> move.currency = company.currency
    >>> move.save()
    >>> move.click('do')

    >>> move.ethanol_volume

Send bottles::

    >>> move = Move()
    >>> move.product = bottle
    >>> move.quantity = 10
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20.00')
    >>> move.currency = company.currency
    >>> move.save()
    >>> move.click('do')

    >>> move.ethanol_volume
    0.5
