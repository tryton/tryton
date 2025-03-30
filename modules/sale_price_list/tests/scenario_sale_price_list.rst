========================
Sale Price List Scenario
========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('sale_price_list', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> customer_without_price_list = Party(name='Customer without price list')
    >>> customer_without_price_list.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

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
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = Decimal('30')
    >>> template.account_category = account_category
    >>> template.save()
    >>> service, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create a price List and assign it to customer::

    >>> PriceList = Model.get('product.price_list')
    >>> price_list = PriceList(name='Retail', price='list_price')
    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.quantity = 10.0
    >>> price_list_line.product = product
    >>> price_list_line.formula = 'unit_price * 0.7'
    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.product = product
    >>> price_list_line.formula = 'unit_price * 0.8'
    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.formula = 'unit_price * 0.5'
    >>> price_list.save()
    >>> customer.sale_price_list = price_list
    >>> customer.save()

Use the price list on sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> assertEqual(sale.price_list, price_list)
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.unit_price
    Decimal('8.0000')
    >>> sale_line.quantity = 12.0
    >>> sale_line.unit_price
    Decimal('7.0000')
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = service
    >>> sale_line.unit_price
    Decimal('15.0000')
    >>> sale_line.quantity = 2.0
    >>> sale_line.unit_price
    Decimal('15.0000')

Create a sale price List and assign to configuration::

    >>> sale_price_list = PriceList(name='Sale price List')
    >>> sale_price_list_line = sale_price_list.lines.new()
    >>> sale_price_list_line.formula = 'unit_price * 0.5'
    >>> sale_price_list.save()
    >>> Configuration = Model.get('sale.configuration')
    >>> config = Configuration(1)
    >>> config.sale_price_list = sale_price_list
    >>> config.save()

Use the sale price list on sale::

    >>> sale.party = customer_without_price_list
    >>> assertEqual(sale.price_list, sale_price_list)
