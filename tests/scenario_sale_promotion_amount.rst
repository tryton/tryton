==============================
Sale Promotion Amount Scenario
==============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('sale_promotion')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> product1 = Product()
    >>> product1.template = template
    >>> product1.save()
    >>> product2 = Product()
    >>> product2.template = template
    >>> product2.save()

Create Promotion::

    >>> Promotion = Model.get('sale.promotion')
    >>> promotion = Promotion(name='product 2 free')
    >>> promotion.amount = Decimal('100')
    >>> promotion.currency = company.currency
    >>> promotion.products.extend([product2])
    >>> promotion.formula = '0.0'
    >>> promotion.save()

Sale enough for promotion::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product1
    >>> sale_line.quantity = 4
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product2
    >>> sale_line.quantity = 2
    >>> sale.save()
    >>> sale.total_amount
    Decimal('120.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('80.00')

Sale not enough for promotion::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product1
    >>> sale_line.quantity = 2
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product2
    >>> sale_line.quantity = 2
    >>> sale.save()
    >>> sale.total_amount
    Decimal('80.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('80.00')
