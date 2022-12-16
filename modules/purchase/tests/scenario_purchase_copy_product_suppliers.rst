========================================
Purchase Copy Product Suppliers Scenario
========================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('purchase')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create party::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create a product with suppliers::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> product_supplier = template.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> template.save()
    >>> product, = template.products
    >>> product_supplier = product.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> product_supplier.template == template
    True
    >>> product.save()

Supplier is copied when copying the template::

    >>> template_copy, = template.duplicate()
    >>> product_copy, = template_copy.products
    >>> len(template_copy.product_suppliers)
    2
    >>> len(product_copy.product_suppliers)
    1
