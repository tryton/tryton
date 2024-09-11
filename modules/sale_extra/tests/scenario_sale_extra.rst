===================
Sale Extra Scenario
===================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import create_payment_term
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_extra', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.lead_time = dt.timedelta(0)
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> extra_template = ProductTemplate()
    >>> extra_template.name = 'Extra'
    >>> extra_template.default_uom = unit
    >>> extra_template.type = 'service'
    >>> extra_template.salable = True
    >>> extra_template.lead_time = dt.timedelta(0)
    >>> extra_template.list_price = Decimal('3')
    >>> extra_template.account_category = account_category
    >>> extra_template.save()
    >>> extra_product, = extra_template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create Extra::

    >>> PriceList = Model.get('product.price_list')
    >>> Extra = Model.get('sale.extra')
    >>> price_list = PriceList(name="Default", price='list_price')
    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.formula = 'unit_price'
    >>> price_list.save()
    >>> extra = Extra(name='Free Extra')
    >>> extra.price_list = price_list
    >>> line = extra.lines.new()
    >>> line.sale_amount = Decimal('100')
    >>> line.product = extra_product
    >>> line.quantity = 2
    >>> line.free = True
    >>> line = extra.lines.new()
    >>> line.sale_amount = Decimal('50')
    >>> line.product = extra_product
    >>> line.quantity = 1
    >>> extra.save()

Sale for 100, 2 free extra added::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list = price_list
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> len(sale.lines)
    1
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> len(sale.lines)
    2
    >>> sum(l.quantity for l in sale.lines)
    7.0

Back to draft, nothing change::

    >>> sale.click('draft')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> len(sale.lines)
    2

Sale for 60, 1 extra added::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list = price_list
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('60.00')
    >>> len(sale.lines)
    1
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('63.00')
    >>> len(sale.lines)
    2

Sale for 20, nothing added::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list = price_list
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('20.00')
    >>> len(sale.lines)
    1
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('20.00')
    >>> len(sale.lines)
    1
