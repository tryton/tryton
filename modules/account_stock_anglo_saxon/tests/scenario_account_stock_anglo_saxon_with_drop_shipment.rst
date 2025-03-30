=====================================================
Account Stock Anglo-Saxon with Drop Shipment Scenario
=====================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.account_stock_anglo_saxon.tests.tools import (
    ...     add_cogs_accounts)
    >>> from trytond.modules.account_stock_continental.tests.tools import (
    ...     add_stock_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'account_stock_anglo_saxon',
    ...         'sale_supply_drop_shipment',
    ...         'sale',
    ...         'purchase',
    ...         ],
    ...     create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.account_stock_method = 'anglo_saxon'
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = add_cogs_accounts(add_stock_accounts(get_accounts()))
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> stock = accounts['stock']
    >>> stock_in = accounts['stock_expense']
    >>> stock_out, = stock_in.duplicate()
    >>> cogs = accounts['cogs']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.account_stock = stock
    >>> account_category.account_cogs = cogs
    >>> account_category.account_stock_in = stock_in
    >>> account_category.account_stock_out = stock_out
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> template.lead_time = dt.timedelta(0)
    >>> template.supply_on_sale = 'always'
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.template = template
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> product_supplier.lead_time = dt.timedelta(0)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 50 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 50
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Create Purchase from Request::

    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find()
    >>> purchase.payment_term = payment_term
    >>> purchase_line, = purchase.lines
    >>> purchase_line.unit_price = Decimal('3')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

Receive 50 products::

    >>> shipment.click('ship')
    >>> shipment.click('do')
    >>> shipment.state
    'done'
    >>> stock_in.reload()
    >>> stock_in.debit
    Decimal('0.00')
    >>> stock_in.credit
    Decimal('150.00')
    >>> stock_out.reload()
    >>> stock_out.debit
    Decimal('150.00')
    >>> stock_out.credit
    Decimal('0.00')
    >>> stock.reload()
    >>> stock.debit
    Decimal('150.00')
    >>> stock.credit
    Decimal('150.00')

Open supplier invoice::

    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> payable.reload()
    >>> payable.debit
    Decimal('0.00')
    >>> payable.credit
    Decimal('150.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('150.00')
    >>> expense.credit
    Decimal('150.00')
    >>> stock_in.reload()
    >>> stock_in.debit
    Decimal('150.00')
    >>> stock_in.credit
    Decimal('150.00')

Open customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('500.00')
    >>> receivable.credit
    Decimal('0.00')
    >>> revenue.reload()
    >>> revenue.debit
    Decimal('0.00')
    >>> revenue.credit
    Decimal('500.00')
    >>> stock_out.reload()
    >>> stock_out.debit
    Decimal('150.00')
    >>> stock_out.credit
    Decimal('150.00')
    >>> cogs.reload()
    >>> cogs.debit
    Decimal('150.00')
    >>> cogs.credit
    Decimal('0.00')
