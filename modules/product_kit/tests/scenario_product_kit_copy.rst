=========================
Product Kit Copy Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate product_kit and stock::

    >>> config = activate_modules('product_kit')

Create company::

    >>> _ = create_company()

Create products::

    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> meter, = Uom.find([('name', '=', "Meter")])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('10.0000')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 2"
    >>> template.default_uom = meter
    >>> template.type = 'goods'
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('20.0000')
    >>> product2.save()

Create a kit::

    >>> template = ProductTemplate()
    >>> template.name = "Kit"
    >>> template.default_uom = unit
    >>> template.type = 'kit'
    >>> template.save()
    >>> kit, = template.products

    >>> component = template.components.new()
    >>> component.product = product1
    >>> component.parent_product = kit
    >>> component.quantity = 1
    >>> component = template.components.new()
    >>> component.product = product2
    >>> component.parent_product = kit
    >>> component.quantity = 1
    >>> component.fixed = True
    >>> template.save()

Components are copied when copying the template::

    >>> template_copy, = template.duplicate()
    >>> product_copy, = template.products
    >>> len(template_copy.components)
    2
    >>> len(product_copy.components)
    2
