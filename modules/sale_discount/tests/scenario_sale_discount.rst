======================
Sale Discount Scenario
======================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('sale_discount')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
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

Create a sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.base_price
    Decimal('10.0000')
    >>> line.unit_price
    Decimal('10.0000')

Set a discount of 10%::

    >>> line.discount_rate = Decimal('0.1')
    >>> line.unit_price
    Decimal('9.0000')
    >>> line.discount_amount
    Decimal('1.0000')
    >>> line.discount
    '10%'

    >>> sale.save()
    >>> line, = sale.lines
    >>> line.unit_price
    Decimal('9.0000')
    >>> line.discount_amount
    Decimal('1.0000')
    >>> line.discount
    '10%'

Set a discount amount::

    >>> line.discount_amount = Decimal('3.3333')
    >>> line.unit_price
    Decimal('6.6667')
    >>> line.discount_rate
    Decimal('0.3333')
    >>> line.discount
    '$3.3333'
