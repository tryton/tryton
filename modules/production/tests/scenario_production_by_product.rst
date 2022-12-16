==========================
Production with By-product
==========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

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
    >>> template.list_price = Decimal(30)
    >>> template.save()
    >>> product, = template.products

Create by-products 1 marketable and 1 waste::

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(10)
    >>> template.save()
    >>> marketable, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(0)
    >>> template.save()
    >>> waste, = template.products

Create component::

    >>> template = ProductTemplate()
    >>> template.name = 'component'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> component, = template.products
    >>> component.cost_price = Decimal(5)
    >>> component.save()

Create Bill of Material::

    >>> BOM = Model.get('production.bom')
    >>> bom = BOM(name='product')
    >>> input = bom.inputs.new()
    >>> input.product = component
    >>> input.quantity = 4
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> output = bom.outputs.new()
    >>> output.product = marketable
    >>> output.quantity = 1
    >>> output = bom.outputs.new()
    >>> output.product = waste
    >>> output.quantity = 2
    >>> bom.save()

Make a production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 4
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.click('done')

Check output price::

    >>> sorted([o.unit_price for o in production.outputs])
    [Decimal('0'), Decimal('5.0000'), Decimal('15.0000')]
