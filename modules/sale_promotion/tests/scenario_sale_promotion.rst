=======================
Sale Promotion Scenario
=======================

Imports::

    >>> import datetime
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_tax, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import create_payment_term
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_promotion', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']

Create a tax::

    >>> tax = create_tax(Decimal('0.1'))

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> Category = Model.get('product.category')

    >>> category = Category(name="Root")
    >>> category1 = category.childs.new(name="Child 1")
    >>> category1b = category1.childs.new(name="Child 1b")
    >>> category2 = category.childs.new(name="Child 2")
    >>> category.save()
    >>> category1, category2 = category.childs
    >>> category1b, = category1.childs

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.lead_time = datetime.timedelta(0)
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.categories.append(Category(category1b.id))
    >>> template.save()
    >>> product1 = Product()
    >>> product1.template = template
    >>> product1.save()
    >>> product2 = Product()
    >>> product2.template = template
    >>> product2.save()
    >>> product3 = Product()
    >>> product3.template = template
    >>> product3.save()

    >>> template4, = template.duplicate(default={'categories': [category2.id]})
    >>> template4.account_category = account_category
    >>> template4.save()
    >>> product4 = Product(template4.products[0].id)

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create Promotion::

    >>> Promotion = Model.get('sale.promotion')
    >>> promotion = Promotion(name='10% on 10 products 1 or 2')
    >>> promotion.quantity = 10
    >>> promotion.unit = unit
    >>> promotion.products.extend([product1, product2, product4])
    >>> promotion.categories.append(Category(category1.id))
    >>> promotion.formula = '0.9 * unit_price'
    >>> promotion.save()

Sale enough products for promotion::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product1
    >>> sale_line.quantity = 5
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product2
    >>> sale_line.quantity = 10
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product3
    >>> sale_line.quantity = 5
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product4
    >>> sale_line.quantity = 5
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('500.00')
    >>> sale.tax_amount
    Decimal('50.00')
    >>> sale.total_amount
    Decimal('550.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('470.00')
    >>> sale.tax_amount
    Decimal('47.00')
    >>> sale.total_amount
    Decimal('517.00')
    >>> sale.original_untaxed_amount
    Decimal('500.00')
    >>> sale.original_tax_amount
    Decimal('50.00')
    >>> sale.original_total_amount
    Decimal('550.00')

Go back to draft reset the original price::

    >>> sale.click('draft')
    >>> sale.untaxed_amount
    Decimal('500.00')

Sale not enough products for promotion::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product1
    >>> sale_line.quantity = 5
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product2
    >>> sale_line.quantity = 3
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product3
    >>> sale_line.quantity = 10
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('360.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('360.00')
