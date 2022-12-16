==================================
Account Stock Anglo-Saxon Scenario
==================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
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

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_stock_continental, sale and purchase::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ('account_stock_anglo_saxon',
    ...             'sale', 'purchase')),
    ...     ])
    >>> for module in modules:
    ...     module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create the required users::

    >>> Group = Model.get('res.group')
    >>> accountant = User()
    >>> accountant.name = 'Accountant'
    >>> accountant.login = 'accountant'
    >>> accountant.password = 'accountant'
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> accountant.groups.append(account_group)
    >>> accountant.save()

    >>> product_user = User()
    >>> product_user.name = 'Product User'
    >>> product_user.login = 'product_user'
    >>> product_user.password = 'product_user'
    >>> product_group, = Group.find([('name', '=', 'Product Administration')])
    >>> product_user.groups.append(product_group)
    >>> product_user.save()

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase User'
    >>> purchase_user.login = 'purchase_user'
    >>> purchase_user.password = 'purchase_user'
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_user.save()

    >>> stock_user = User()
    >>> stock_user.name = 'Sale User'
    >>> stock_user.login = 'stock_user'
    >>> stock_user.password = 'stock_user'
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
    >>> stock_customer = accounts['stock_customer']
    >>> stock_lost_found = accounts['stock_lost_found']
    >>> stock_production = accounts['stock_production']
    >>> stock_supplier = accounts['stock_supplier']
    >>> cogs = accounts['cogs']

    >>> AccountJournal = Model.get('account.journal')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.lead_time = datetime.timedelta(0)
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.account_stock = stock
    >>> template.account_cogs = cogs
    >>> template.account_stock_supplier = stock_supplier
    >>> template.account_stock_customer = stock_customer
    >>> template.account_stock_production = stock_production
    >>> template.account_stock_lost_found = stock_lost_found
    >>> template.account_journal_stock_supplier = stock_journal
    >>> template.account_journal_stock_customer = stock_journal
    >>> template.account_journal_stock_lost_found = stock_journal
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> template_average, = ProductTemplate.duplicate([template])
    >>> template_average.cost_price_method = 'average'
    >>> template_average.save()
    >>> product_average, = Product.duplicate([product], {
    ...         'template': template_average.id,
    ...         })

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
    >>> purchase.click('process')
    >>> purchase.state
    u'processing'

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
    u'done'
    >>> stock_supplier.reload()
    >>> stock.reload()
    >>> stock_supplier.debit
    Decimal('0.00')
    >>> stock_supplier.credit
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
    u'posted'
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
    >>> stock_supplier.reload()
    >>> stock_supplier.debit
    Decimal('46.00')
    >>> stock_supplier.credit
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
    >>> sale.click('process')
    >>> sale.state
    u'processing'

Send 5 products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> shipment.click('assign_try')
    True
    >>> shipment.state
    u'assigned'
    >>> shipment.click('pack')
    >>> shipment.state
    u'packed'
    >>> shipment.click('done')
    >>> shipment.state
    u'done'
    >>> stock_customer.reload()
    >>> stock_customer.debit
    Decimal('28.00')
    >>> stock_customer.credit
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
    u'posted'
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
    >>> stock_customer.reload()
    >>> stock_customer.debit
    Decimal('28.00')
    >>> stock_customer.credit
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
    >>> purchase.click('process')
    >>> purchase.state
    u'processing'

    >>> config.user = accountant.id
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
    u'posted'
    >>> move = invoice.move
    >>> line_cogs, = (l for l in move.lines if l.account == cogs)
    >>> line_cogs.credit
    Decimal('5.00')
    >>> line_stock, = (l for l in move.lines if l.account == stock_customer)
    >>> line_stock.debit
    Decimal('5.00')

Now we will use a product with different unit of measure::

    >>> config.user = product_user.id
    >>> UomCategory = Model.get('product.uom.category')
    >>> unit_category, = UomCategory.find([('name', '=', 'Units')])
    >>> unit_5 = ProductUom(name='5', symbol='5', category=unit_category,
    ...    factor=5, digits=0)
    >>> unit_5.save()

    >>> product_by5 = Product()
    >>> template_by5 = ProductTemplate()
    >>> template_by5.name = 'product'
    >>> template_by5.default_uom = unit
    >>> template_by5.type = 'goods'
    >>> template_by5.purchasable = True
    >>> template_by5.purchase_uom = unit_5
    >>> template_by5.salable = True
    >>> template_by5.sale_uom = unit_5
    >>> template_by5.list_price = Decimal('10')
    >>> template_by5.cost_price = Decimal('5')
    >>> template_by5.cost_price_method = 'fixed'
    >>> template_by5.lead_time = datetime.timedelta(0)
    >>> template_by5.account_expense = expense
    >>> template_by5.account_revenue = revenue
    >>> template_by5.account_stock = stock
    >>> template_by5.account_cogs = cogs
    >>> template_by5.account_stock_supplier = stock_supplier
    >>> template_by5.account_stock_customer = stock_customer
    >>> template_by5.account_stock_production = stock_production
    >>> template_by5.account_stock_lost_found = stock_lost_found
    >>> template_by5.account_journal_stock_supplier = stock_journal
    >>> template_by5.account_journal_stock_customer = stock_journal
    >>> template_by5.account_journal_stock_lost_found = stock_journal
    >>> template_by5.save()
    >>> product_by5.template = template_by5
    >>> product_by5.save()

    >>> config.user = purchase_user.id
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'shipment'
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product_by5
    >>> purchase_line.quantity = 1.0
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')

    >>> config.user = stock_user.id
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move = Move(purchase.moves[0].id)
    >>> move.in_anglo_saxon_quantity
    0.0
    >>> shipment.incoming_moves.append(move)
    >>> shipment.click('receive')
    >>> shipment.click('done')

    >>> config.user = accountant.id
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'

    >>> config.user = stock_user.id
    >>> move = Move(purchase.moves[0].id)
    >>> move.in_anglo_saxon_quantity
    1.0
