==============================
Sale Product Quantity Scenario
==============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_product_quantity', create_company)

    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create product::

    >>> gr, = ProductUom.find([('name', '=', "Gram")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = gr
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10')
    >>> template.salable = True
    >>> template.sale_uom = kg
    >>> template.sale_quantity_minimal = 0.1
    >>> template.sale_quantity_rounding = 0.05
    >>> template.save()
    >>> product, = template.products

Make a sale::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity
    0.1
    >>> sale.save()

Can not set quantity below minimal::

    >>> line, = sale.lines
    >>> line.quantity = 0.05
    >>> sale.save()
    Traceback (most recent call last):
        ...
    SaleValidationError: ...

Can not set quantity different than rounding::

    >>> line, = sale.lines
    >>> line.quantity = 1.01
    >>> sale.save()
    Traceback (most recent call last):
        ...
    SaleValidationError: ...

Use different unit::

    >>> line, = sale.lines
    >>> line.unit = gr
    >>> line.quantity = 500
    >>> sale.save()

Can not set quantity below minimal::

    >>> line, = sale.lines
    >>> line.quantity = 50
    >>> sale.save()
    Traceback (most recent call last):
        ...
    SaleValidationError: ...

Can not set quantity different than rounding::

    >>> line, = sale.lines
    >>> line.quantity = 505
    >>> sale.save()
    Traceback (most recent call last):
        ...
    SaleValidationError: ...
