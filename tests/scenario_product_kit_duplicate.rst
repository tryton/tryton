==============================
Product Kit Duplicate Scenario
==============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate product_kit::

    >>> config = activate_modules('product_kit')

    >>> Uom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create products::

    >>> unit, = Uom.find([('name', '=', 'Unit')])
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
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('20.0000')
    >>> product2.save()

Create composed product::

    >>> template = ProductTemplate()
    >>> template.name = "Composed Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> composed_product, = template.products
    >>> composed_product.cost_price = Decimal('10.0000')

    >>> component = composed_product.components.new()
    >>> component.product = product1
    >>> component.quantity = 2
    >>> composed_product.save()

Create a kit::

    >>> template = ProductTemplate()
    >>> template.name = "Kit"
    >>> template.default_uom = unit
    >>> template.type = 'kit'
    >>> template.save()
    >>> kit, = template.products

    >>> component = template.components.new()
    >>> component.product = product1
    >>> component.quantity = 1
    >>> component = template.components.new()
    >>> component.product = product2
    >>> component.quantity = 2
    >>> template.save()

Test duplicate copies components::

    >>> duplicated, = template.duplicate()
    >>> len(duplicated.components)
    2
    >>> duplicated_product, = composed_product.duplicate()
    >>> len(duplicated_product.components)
    1
