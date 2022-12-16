========================
Sale Price List Scenario
========================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term

Activate modules::

    >>> config = activate_modules('sale_price_list')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create sale user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_user.main_company = company
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

    >>> sale_admin = User()
    >>> sale_admin.name = 'Sale Admin'
    >>> sale_admin.login = 'sale_admin'
    >>> sale_admin.main_company = company
    >>> sale_admin_group, = Group.find([('name', '=', 'Sales Administrator')])
    >>> sale_admin.groups.append(sale_admin_group)
    >>> product_admin_group, = Group.find(
    ...     [('name', '=', 'Product Administration')])
    >>> sale_admin.groups.append(product_admin_group)
    >>> sale_admin.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
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
    >>> price_list = PriceList(name='Retail')
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

    >>> set_user(sale_user)
    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list == price_list
    True
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

    >>> set_user(sale_admin)
    >>> sale_price_list = PriceList(name='Sale price List')
    >>> sale_price_list_line = sale_price_list.lines.new()
    >>> sale_price_list_line.formula = 'unit_price * 0.5'
    >>> sale_price_list.save()
    >>> Configuration = Model.get('sale.configuration')
    >>> config = Configuration()
    >>> config.sale_price_list = sale_price_list
    >>> config.save()

Use the sale price list on sale::

    >>> set_user(sale_user)
    >>> sale.party = customer_without_price_list
    >>> sale.price_list == sale_price_list
    True
