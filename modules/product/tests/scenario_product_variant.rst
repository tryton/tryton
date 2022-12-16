========================
Product Variant Scenario
========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('product')

Create a template::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.list_price = Decimal('42.0000')
    >>> template.code = "PROD"
    >>> template.save()
    >>> len(template.products)
    1
    >>> product, = template.products
    >>> product.code
    'PROD'
    >>> product.suffix_code = "001"
    >>> product.save()
    >>> product.code
    'PROD001'

Create a variant::

    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> product.template = template
    >>> product.name
    'Product'
    >>> product.list_price
    Decimal('42.0000')
    >>> product.suffix_code = "002"
    >>> product.save()
    >>> product.list_price
    Decimal('42.0000')
    >>> product.code
    'PROD002'

Change template code::

    >>> template.code = "PRD"
    >>> template.save()
    >>> sorted([p.code for p in template.products])
    ['PRD001', 'PRD002']
