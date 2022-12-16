===================
Sale Stock Quantity
===================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.stock.exceptions import InventoryFutureWarning
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules(['sale_stock_quantity', 'stock_supply'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

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
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.template = template
    >>> product_supplier.party = supplier
    >>> product_supplier.lead_time = datetime.timedelta(3)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an Inventory of 5 products::

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 5.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Sale 3 products with enough stock::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale.click('quote')

Sale 1 product with still enough stock::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale.click('quote')

Sale 2 more products with not enough stock::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote') # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    StockQuantityWarning: ...

Clean sales::

    >>> Sale.delete(Sale.find([]))

Sale 6 products with not enough stock::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 6.0
    >>> sale.click('quote') # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    StockQuantityWarning: ...
    >>> sale.delete()

Make an inventory of 3 products in 2 days::

    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.date = today + datetime.timedelta(2)
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 3.0
    >>> inventory_line.expected_quantity = 5.0
    >>> try:
    ...     inventory.click('confirm')
    ... except InventoryFutureWarning as e:
    ...     Model.get('res.user.warning')(user=config.user, name=e.name).save()
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Sale 4 products with not enough forecast::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 4.0
    >>> sale.click('quote') # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    StockQuantityWarning: ...
    >>> sale.delete()

Sale 2 products with enough forecast::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote')
    >>> sale.delete()
