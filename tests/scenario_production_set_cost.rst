===================
Production Set Cost
===================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Install production Module::

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
    >>> input.quantity = 2
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

Make a production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.click('done')

Check output price::

    >>> production.cost
    Decimal('20.0000')
    >>> output, = production.outputs
    >>> output.unit_price
    Decimal('10.0000')


Change cost of input::

    >>> Move = Model.get('stock.move')
    >>> input, = production.inputs
    >>> Move.write([input], {'cost_price': Decimal(6)}, config.context)
    >>> input.reload()
    >>> bool(input.production_cost_price_updated)
    True

Launch cron task::

    >>> Cron = Model.get('ir.cron')
    >>> Company = Model.get('company.company')
    >>> cron_set_cost, = Cron.find([
    ...     ('method', '=', 'production|set_cost_from_moves'),
    ...     ])
    >>> cron_set_cost.companies.append(Company(company.id))
    >>> cron_set_cost.click('run_once')

    >>> output.reload()
    >>> output.unit_price
    Decimal('12.0000')
    >>> input.reload()
    >>> bool(input.production_cost_price_updated)
    False
