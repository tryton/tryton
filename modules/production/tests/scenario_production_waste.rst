=========================
Production Waste Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('production')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create main product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create Component::

    >>> template = ProductTemplate()
    >>> template.name = 'component 1'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(50)
    >>> component, = template.products
    >>> component.cost_price = Decimal(1)
    >>> template.save()
    >>> component, = template.products

Configure locations::

    >>> Location = Model.get('stock.location')
    >>> lost_found_loc, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse_loc, = Location.find([('type', '=', 'warehouse')])
    >>> warehouse_loc.waste_locations.append(lost_found_loc)
    >>> warehouse_loc.save()

Run the production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> input = production.inputs.new()
    >>> input.quantity = 20.0
    >>> input.product = component
    >>> input.from_location = warehouse_loc.storage_location
    >>> input.to_location = production.location
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')

Create outputs including waste products::

    >>> output = production.outputs.new()
    >>> output.quantity = 1.0
    >>> output.product = product
    >>> output.from_location = production.location
    >>> output.to_location = warehouse_loc.storage_location
    >>> output.unit_price = Decimal('0')
    >>> waste_output = production.outputs.new()
    >>> waste_output.quantity = 1.0
    >>> waste_output.product = product
    >>> waste_output.from_location = production.location
    >>> waste_output.to_location = lost_found_loc
    >>> production.click('done')
    >>> production.cost
    Decimal('20.0000')
    >>> output, = [o for o in production.outputs
    ...     if o.to_location.type != 'lost_found']
    >>> output.unit_price
    Decimal('20.0000')
    >>> waste_output, = [o for o in production.outputs
    ...     if o.to_location.type == 'lost_found']
    >>> waste_output.unit_price
