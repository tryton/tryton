========================
Product Variant Scenario
========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('product', create_company)

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
    >>> product1, = template.products
    >>> product1.code
    'PROD'
    >>> product1.suffix_code = "001"
    >>> product1.save()
    >>> product1.code
    'PROD001'

Create a variant::

    >>> Product = Model.get('product.product')
    >>> product2 = Product()
    >>> product2.template = template
    >>> product2.name
    'Product'
    >>> product2.suffix_code = "002"
    >>> product2.save()
    >>> product2.list_price_used
    Decimal('42.0000')
    >>> product2.code
    'PROD002'

Change variant list price::

    >>> product2.list_price = Decimal('50.0000')
    >>> product2.save()
    >>> product2.list_price
    Decimal('50.0000')
    >>> product2.list_price_used
    Decimal('50.0000')

    >>> product1.reload()
    >>> product1.list_price
    >>> product1.list_price_used
    Decimal('42.0000')

    >>> template.reload()
    >>> template.list_price
    Decimal('42.0000')

Change product list price::

    >>> template.list_price = Decimal('40.0000')
    >>> template.save()

    >>> product2.reload()
    >>> product2.list_price
    Decimal('50.0000')
    >>> product2.list_price_used
    Decimal('50.0000')

    >>> product1.reload()
    >>> product1.list_price
    >>> product1.list_price_used
    Decimal('40.0000')

Change template code::

    >>> template.code = "PRD"
    >>> template.save()
    >>> sorted([p.code for p in template.products])
    ['PRD001', 'PRD002']

Create template with trailing space in code::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.code = "TRAILING "
    >>> template.default_uom = unit
    >>> template.save()
    >>> product, = template.products
    >>> product.code
    'TRAILING'

Create product with leading space in code::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> product, = template.products
    >>> product.suffix_code = " LEADING"
    >>> template.save()
    >>> product, = template.products
    >>> product.code
    'LEADING'
