===================================
Sale Copy Product Customer Scenario
===================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('sale_product_customer')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='customer')
    >>> customer.save()

Create a product with customers::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> product_customer = template.product_customers.new()
    >>> product_customer.party = customer
    >>> template.save()
    >>> product, = template.products
    >>> product_customer = product.product_customers.new()
    >>> product_customer.party = customer
    >>> product_customer.template == template
    True
    >>> product.save()

Customer is copied when copying the template::

    >>> template_copy, = template.duplicate()
    >>> product_copy, = template_copy.products
    >>> len(template_copy.product_customers)
    2
    >>> len(product_copy.product_customers)
    1
