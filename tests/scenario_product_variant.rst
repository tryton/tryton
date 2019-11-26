========================
Product Variant Scenario
========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Install party::

    >>> config = activate_modules('product')

Create a template::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.list_price = Decimal('42.0000')
    >>> template.save()
    >>> len(template.products)
    1

Create a variant::

    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> product.template = template
    >>> product.name
    'Product'
    >>> product.list_price
    Decimal('42.0000')
    >>> product.save()
    >>> product.list_price
    Decimal('42.0000')
