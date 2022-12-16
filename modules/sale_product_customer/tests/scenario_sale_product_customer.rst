==============================
Sale Product Customer Scenario
==============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Activate modules::

    >>> config = activate_modules('sale_product_customer')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.save()
    >>> product, = template.products
    >>> product_customer = product.product_customers.new()
    >>> product_customer.party = customer
    >>> product_customer.code = 'CUST'
    >>> product.save()

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()

Check filling product customer::

    >>> line.product = product
    >>> line.product_customer.code
    'CUST'

Add product customer to the template::

    >>> product_customer2 = template.product_customers.new()
    >>> product_customer2.party = customer
    >>> product_customer2.code = 'TEMPCUST'
    >>> template.save()

Count product linked to customer::

    >>> ProductCustomer = Model.get('sale.product_customer')
    >>> products = ProductCustomer.find(
    ...     [('party', '=', customer.id)])
    >>> len(products) == 2
    True
