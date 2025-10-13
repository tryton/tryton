===============================
Production Phantom BOM Scenario
===============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('production')

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> BOM = Model.get('production.bom')
    >>> BOMInput = Model.get('production.bom.input')
    >>> BOMOutput = Model.get('production.bom.output')
    >>> ProductBom = Model.get('product.product-production.bom')
    >>> Production = Model.get('production')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template_table = ProductTemplate()
    >>> template_table.name = 'table'
    >>> template_table.default_uom = unit
    >>> template_table.type = 'goods'
    >>> template_table.producible = True
    >>> template_table.list_price = Decimal(30)
    >>> table, = template_table.products
    >>> table.cost_price = Decimal(20)
    >>> template_table.save()
    >>> table, = template_table.products

Create Components::

    >>> template_top = ProductTemplate()
    >>> template_top.name = 'top'
    >>> template_top.default_uom = unit
    >>> template_top.type = 'goods'
    >>> template_top.list_price = Decimal(5)
    >>> top, = template_top.products
    >>> top.cost_price = Decimal(1)
    >>> template_top.save()
    >>> top, = template_top.products

    >>> template_leg = ProductTemplate()
    >>> template_leg.name = 'leg'
    >>> template_leg.default_uom = unit
    >>> template_leg.type = 'goods'
    >>> template_leg.producible = True
    >>> template_leg.list_price = Decimal(7)
    >>> template_leg.producible = True
    >>> leg, = template_leg.products
    >>> leg.cost_price = Decimal(5)
    >>> template_leg.save()
    >>> leg, = template_leg.products

    >>> template_foot = ProductTemplate()
    >>> template_foot.name = 'foot'
    >>> template_foot.default_uom = unit
    >>> template_foot.type = 'goods'
    >>> template_foot.list_price = Decimal(5)
    >>> foot, = template_foot.products
    >>> foot.cost_price = Decimal(3)
    >>> template_foot.save()
    >>> foot, = template_foot.products

    >>> template_extension = ProductTemplate()
    >>> template_extension.name = 'extension'
    >>> template_extension.default_uom = unit
    >>> template_extension.type = 'goods'
    >>> template_extension.list_price = Decimal(5)
    >>> extension, = template_extension.products
    >>> extension.cost_price = Decimal(4)
    >>> template_extension.save()
    >>> extension, = template_extension.products

    >>> template_hook = ProductTemplate()
    >>> template_hook.name = 'hook'
    >>> template_hook.default_uom = unit
    >>> template_hook.type = 'goods'
    >>> template_hook.list_price = Decimal(7)
    >>> hook, = template_hook.products
    >>> hook.cost_price = Decimal(9)
    >>> template_hook.save()
    >>> hook, = template_hook.products

Create Phantom Bill of Material with input products::

    >>> phantom_bom_input = BOM(name='Leg Foot Input')
    >>> phantom_bom_input.phantom = True
    >>> phantom_bom_input.phantom_quantity = 1
    >>> phantom_bom_input.phantom_unit = unit
    >>> phantom_input1 = phantom_bom_input.inputs.new()
    >>> phantom_input1.product = leg
    >>> phantom_input1.quantity = 1
    >>> phantom_input2 = phantom_bom_input.inputs.new()
    >>> phantom_input2.product = foot
    >>> phantom_input2.quantity = 1
    >>> phantom_bom_input.save()

Create Phantom Bill of Material with output products::

    >>> phantom_bom_output = BOM(name='Extension Hook Ouput')
    >>> phantom_bom_output.phantom = True
    >>> phantom_bom_output.phantom_quantity = 1
    >>> phantom_bom_output.phantom_unit = unit
    >>> phantom_output1 = phantom_bom_output.outputs.new()
    >>> phantom_output1.product = extension
    >>> phantom_output1.quantity = 1
    >>> phantom_output2 = phantom_bom_output.outputs.new()
    >>> phantom_output2.product = hook
    >>> phantom_output2.quantity = 2
    >>> phantom_bom_output.save()
    >>> phantom_bom_output.outputs[0].product.name
    'extension'
    >>> phantom_bom_output.outputs[1].product.name
    'hook'

Create Bill of Material using Phantom BoM::

    >>> bom = BOM(name='product with Phantom BoM')
    >>> input1 = bom.inputs.new()
    >>> input1.product = top
    >>> input1.quantity = 1
    >>> input2 = bom.inputs.new()
    >>> input2.phantom_bom = phantom_bom_input
    >>> input2.quantity = 4
    >>> output = bom.outputs.new()
    >>> output.product = table
    >>> output.quantity = 1
    >>> output2 = bom.outputs.new()
    >>> output2.phantom_bom = phantom_bom_output
    >>> output2.quantity = 2
    >>> bom.save()

    >>> table.boms.append(ProductBom(bom=bom))
    >>> table.save()
