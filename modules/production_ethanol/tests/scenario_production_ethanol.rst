===========================
Production Ethanol Scenario
===========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('production_ethanol')

    >>> Location = Model.get('stock.location')
    >>> ProductTemplate = Model.get('product.template')
    >>> Production = Model.get('production')
    >>> ProductionConfiguration = Model.get('production.configuration')
    >>> Uom = Model.get('product.uom')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> production_loc, = Location.find([('code', '=', 'PROD')])

Create products::

    >>> liter, = Uom.find([('name', '=', "Liter")])
    >>> kg, = Uom.find([('name', '=', "Kilogram")])
    >>> unit, = Uom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Cork"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.contain_ethanol = False
    >>> template.save()
    >>> cork, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Distillate"
    >>> template.default_uom = liter
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20.0000')
    >>> template.contain_ethanol = True
    >>> template.ethanol_by_volume = 0.5
    >>> template.save()
    >>> distillate, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Water"
    >>> template.default_uom = liter
    >>> template.type = 'goods'
    >>> template.consumable = True
    >>> template.save()
    >>> water, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Bottle"
    >>> template.default_uom = liter
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20.0000')
    >>> template.contain_ethanol = True
    >>> template.ethanol_by_volume = 0.1
    >>> template.save()
    >>> bottle, = template.products

Make a production of bottle::

    >>> production = Production()
    >>> input = production.inputs.new()
    >>> input.product = distillate
    >>> input.quantity = 3
    >>> input.from_location = storage_loc
    >>> input.to_location = production_loc
    >>> input = production.inputs.new()
    >>> input.product = cork
    >>> input.quantity = 10
    >>> input.from_location = storage_loc
    >>> input.to_location = production_loc
    >>> input = production.inputs.new()
    >>> input.product = water
    >>> input.quantity = 8
    >>> input.from_location = storage_loc
    >>> input.to_location = production_loc
    >>> output = production.outputs.new()
    >>> output.product = bottle
    >>> output.quantity = 10
    >>> output.from_location = production_loc
    >>> output.to_location = storage_loc
    >>> output.unit_price = Decimal('20.0000')
    >>> output.currency = company.currency
    >>> production.save()

Check ethanol volume::

    >>> production.ethanol_volume
    -0.5
