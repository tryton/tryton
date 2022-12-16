==================================
Account Stock Anglo-Saxon Scenario
==================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.account_stock_continental.tests.tools import \
    ...     add_stock_accounts
    >>> from trytond.modules.account_stock_anglo_saxon.tests.tools import \
    ...     add_cogs_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'account_stock_anglo_saxon',
    ...         'sale',
    ...         'purchase',
    ...         ])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create the required users::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> accountant = User()
    >>> accountant.name = 'Accountant'
    >>> accountant.login = 'accountant'
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> accountant.groups.append(account_group)
    >>> accountant.save()

    >>> product_user = User()
    >>> product_user.name = 'Product User'
    >>> product_user.login = 'product_user'
    >>> product_group, = Group.find([('name', '=', 'Product Administration')])
    >>> product_user.groups.append(product_group)
    >>> product_user.save()

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase User'
    >>> purchase_user.login = 'purchase_user'
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_user.save()

    >>> stock_user = User()
    >>> stock_user.name = 'Sale User'
    >>> stock_user.login = 'stock_user'
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.account_stock_method = 'anglo_saxon'
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = add_cogs_accounts(add_stock_accounts(
    ...         get_accounts(company), company), company)
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
    >>> template.lead_time = datetime.timedelta(0)
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products
    >>> template_average, = template.duplicate({'cost_price_method': 'average'})
    >>> product_average, = template_average.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Purchase 12 products::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'shipment'
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5.0
    >>> purchase_line.unit_price = Decimal(4)
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product_average
    >>> purchase_line.quantity = 7.0
    >>> purchase_line.unit_price = Decimal(6)
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Receive 9 products::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move, = [m for m in purchase.moves if m.product == product]
    >>> move = Move(move.id)
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 4.0
    >>> move, = [m for m in purchase.moves if m.product == product_average]
    >>> move = Move(move.id)
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 5.0
    >>> shipment.click('receive')
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> stock_in.reload()
    >>> stock.reload()
    >>> stock_in.debit
    Decimal('0.00')
    >>> stock_in.credit
    Decimal('46.00')
    >>> stock.reload()
    >>> stock.debit
    Decimal('50.00')
    >>> stock.credit
    Decimal('0.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('0.00')
    >>> expense.credit
    Decimal('4.00')

Open supplier invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice_line, = [l for l in invoice.lines if l.product == product]
    >>> invoice_line.unit_price = Decimal('6')
    >>> invoice_line, = [l for l in invoice.lines
    ...     if l.product == product_average]
    >>> invoice_line.unit_price = Decimal('4')
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> payable.reload()
    >>> payable.debit
    Decimal('0.00')
    >>> payable.credit
    Decimal('44.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('44.00')
    >>> expense.credit
    Decimal('50.00')
    >>> stock_in.reload()
    >>> stock_in.debit
    Decimal('46.00')
    >>> stock_in.credit
    Decimal('46.00')

Sale 5 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product_average
    >>> sale_line.quantity = 3.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Send 5 products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> shipment.click('assign_try')
    True
    >>> shipment.state
    'assigned'
    >>> shipment.click('pick')
    >>> shipment.state
    'picked'
    >>> shipment.click('pack')
    >>> shipment.state
    'packed'
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> stock_out.reload()
    >>> stock_out.debit
    Decimal('28.00')
    >>> stock_out.credit
    Decimal('0.00')
    >>> stock.reload()
    >>> stock.debit
    Decimal('50.00')
    >>> stock.credit
    Decimal('28.00')

Open customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('50.00')
    >>> receivable.credit
    Decimal('0.00')
    >>> revenue.reload()
    >>> revenue.debit
    Decimal('0.00')
    >>> revenue.credit
    Decimal('50.00')
    >>> stock_out.reload()
    >>> stock_out.debit
    Decimal('28.00')
    >>> stock_out.credit
    Decimal('28.00')
    >>> cogs.reload()
    >>> cogs.debit
    Decimal('28.00')
    >>> cogs.credit
    Decimal('0.00')

Now create a supplier invoice with an accountant::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5.0
    >>> purchase_line.unit_price = Decimal(4)
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

    >>> set_user(accountant)
    >>> for invoice in purchase.invoices:
    ...     invoice.invoice_date = today
    >>> Invoice.save(purchase.invoices)
    >>> Invoice.click(purchase.invoices, 'validate_invoice')

Create customer invoice with negative quantity::

    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> invoice.payment_term = payment_term
    >>> invoice_line = invoice.lines.new()
    >>> invoice_line.product = product
    >>> invoice_line.quantity = -1
    >>> invoice_line.unit_price = Decimal('10')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> move = invoice.move
    >>> line_cogs, = (l for l in move.lines if l.account == cogs)
    >>> line_cogs.credit
    Decimal('5.00')
    >>> line_stock, = (l for l in move.lines if l.account == stock_in)
    >>> line_stock.debit
    Decimal('5.00')

Now we will use a product with different unit of measure::

    >>> set_user(product_user)
    >>> UomCategory = Model.get('product.uom.category')
    >>> unit_category, = UomCategory.find([('name', '=', 'Units')])
    >>> unit_5 = ProductUom(name='5', symbol='5', category=unit_category,
    ...    factor=5, digits=0, rounding=1)
    >>> unit_5.save()

    >>> template_by5 = ProductTemplate()
    >>> template_by5.name = 'product'
    >>> template_by5.default_uom = unit
    >>> template_by5.type = 'goods'
    >>> template_by5.purchasable = True
    >>> template_by5.purchase_uom = unit_5
    >>> template_by5.salable = True
    >>> template_by5.sale_uom = unit_5
    >>> template_by5.list_price = Decimal('10')
    >>> template_by5.cost_price_method = 'fixed'
    >>> template_by5.lead_time = datetime.timedelta(0)
    >>> template_by5.account_category = account_category
    >>> product_by5, = template_by5.products
    >>> product_by5.cost_price = Decimal('5')
    >>> template_by5.save()
    >>> product_by5, = template_by5.products

    >>> set_user(purchase_user)
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'shipment'
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product_by5
    >>> purchase_line.quantity = 1.0
    >>> purchase.click('quote')
    >>> purchase.click('confirm')

    >>> set_user(stock_user)
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move = Move(purchase.moves[0].id)
    >>> move.in_anglo_saxon_quantity
    0.0
    >>> shipment.incoming_moves.append(move)
    >>> shipment.click('receive')
    >>> shipment.click('done')

    >>> set_user(accountant)
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> set_user(stock_user)
    >>> move = Move(purchase.moves[0].id)
    >>> move.in_anglo_saxon_quantity
    1.0
