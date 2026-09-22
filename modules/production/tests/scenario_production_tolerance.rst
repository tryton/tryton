=============================
Production Tolerance Scenario
=============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('production', create_company)

    >>> BOM = Model.get('production.bom')
    >>> ProductBOM = Model.get('product.product-production.bom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Production = Model.get('production')
    >>> UoM = Model.get('product.uom')

Create products::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Component"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.0000')
    >>> template.save()
    >>> component, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal('20.0000')
    >>> template.save()
    >>> product, = template.products

Create a bill of material::

    >>> bom = BOM(name="Product")
    >>> input = bom.inputs.new()
    >>> input.product = component
    >>> input.quantity = 2
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.tolerance = 10 / 100
    >>> bom.save()

    >>> product.boms.append(ProductBOM(bom=bom))
    >>> product.save()

Make a production::

    >>> production = Production()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 10
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.state
    'running'

Try under produce::

    >>> output, = production.outputs
    >>> output.quantity = 8
    >>> production.click('do')
    Traceback (most recent call last):
        ...
    UnderProductionWarning: ... 8.0 u produced < 9.0 u ...

Try over produce::

    >>> output, = production.outputs
    >>> output.quantity = 12
    >>> production.click('do')
    Traceback (most recent call last):
        ...
    OverProductionWarning: ... 12.0 u produced < 11.0 u ...

    >>> output, = production.outputs
    >>> output.quantity = 9
    >>> production.save()

Try unexpected product::

    >>> output = production.outputs.new()
    >>> output.from_location = production.location
    >>> output.to_location = production.warehouse.storage_location
    >>> output.product = component
    >>> output.quantity = 1
    >>> output.unit_price = Decimal(0)
    >>> production.click('do')
    Traceback (most recent call last):
        ...
    UnexpectedProductionWarning: ...

    >>> output, = [m for m in production.outputs if m.product == component]
    >>> _ = production.outputs.remove(output)
    >>> production.save()

Produce inside tolerance::

    >>> production.click('do')
    >>> production.state
    'done'
