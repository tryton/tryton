=================
Purchase Scenario
=================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install purchase::

    >>> Module = Model.get('ir.module')
    >>> purchase_module, = Module.find([('name', '=', 'purchase')])
    >>> purchase_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create purchase user::

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_user.save()

Create stock user::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create account user::

    >>> account_user = User()
    >>> account_user.name = 'Account'
    >>> account_user.login = 'account'
    >>> account_user.main_company = company
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> account_user.groups.append(account_group)
    >>> account_user.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

    >>> Journal = Model.get('account.journal')
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.credit_account = cash
    >>> cash_journal.debit_account = cash
    >>> cash_journal.save()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

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
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.supplier_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

    >>> service = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> service.template = template
    >>> service.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an Inventory::

    >>> config.user = stock_user.id
    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    u'done'

Purchase 5 products::

    >>> config.user = purchase_user.id
    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseLine = Model.get('purchase.line')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 2.0
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.type = 'comment'
    >>> purchase_line.description = 'Comment'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 3.0
    >>> purchase.click('quote')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> purchase.click('confirm')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> purchase.click('process')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> purchase.state
    u'processing'
    >>> len(purchase.moves), len(purchase.shipment_returns), len(purchase.invoices)
    (2, 0, 1)
    >>> invoice, = purchase.invoices
    >>> invoice.origins == purchase.rec_name
    True

Invoice line must be linked to stock move::

    >>> _, invoice_line1, invoice_line2 = sorted(invoice.lines,
    ...     key=lambda l: l.quantity or 0)
    >>> stock_move1, stock_move2 = sorted(purchase.moves,
    ...     key=lambda m: m.quantity)
    >>> invoice_line1.stock_moves == [stock_move1]
    True
    >>> stock_move1.invoice_lines == [invoice_line1]
    True
    >>> invoice_line2.stock_moves == [stock_move2]
    True
    >>> stock_move2.invoice_lines == [invoice_line2]
    True

Post invoice and check no new invoices::

    >>> config.user = account_user.id
    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(purchase.invoices[0].id)
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> config.user = purchase_user.id
    >>> purchase.reload()
    >>> len(purchase.moves), len(purchase.shipment_returns), len(purchase.invoices)
    (2, 0, 1)

Purchase 5 products with an invoice method 'on shipment'::

    >>> config.user = purchase_user.id
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'shipment'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 2.0
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.type = 'comment'
    >>> purchase_line.description = 'Comment'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 3.0
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> len(purchase.moves), len(purchase.shipment_returns), len(purchase.invoices)
    (2, 0, 0)

Not yet linked to invoice lines::

    >>> stock_move1, stock_move2 = sorted(purchase.moves,
    ...     key=lambda m: m.quantity)
    >>> len(stock_move1.invoice_lines)
    0
    >>> len(stock_move2.invoice_lines)
    0

Validate Shipments::

    >>> config.user = stock_user.id
    >>> Move = Model.get('stock.move')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> for move in purchase.moves:
    ...     incoming_move = Move(id=move.id)
    ...     shipment.incoming_moves.append(incoming_move)
    >>> shipment.save()
    >>> shipment.origins == purchase.rec_name
    True
    >>> shipment.click('receive')
    >>> shipment.click('done')
    >>> purchase.reload()
    >>> len(purchase.shipments), len(purchase.shipment_returns)
    (1, 0)

Open supplier invoice::

    >>> config.user = purchase_user.id
    >>> invoice, = purchase.invoices
    >>> config.user = account_user.id
    >>> invoice = Invoice(invoice.id)
    >>> invoice.type
    u'in'
    >>> invoice_line1, invoice_line2 = sorted(invoice.lines,
    ...     key=lambda l: l.quantity or 0)
    >>> for line in invoice.lines:
    ...     line.quantity = 1
    ...     line.save()
    >>> invoice.invoice_date = today
    >>> invoice.click('post')

Invoice lines must be linked to each stock moves::

    >>> invoice_line1.stock_moves == [stock_move1]
    True
    >>> invoice_line2.stock_moves == [stock_move2]
    True

Check second invoices::

    >>> config.user = purchase_user.id
    >>> purchase.reload()
    >>> len(purchase.invoices)
    2
    >>> sum(l.quantity for i in purchase.invoices for l in i.lines)
    5.0

Create the report::

    >>> purchase_report = Report('purchase.purchase')
    >>> ext, _, _, name = purchase_report.execute([purchase], {})
    >>> ext
    u'odt'
    >>> name
    u'Purchase'

Create a Return::

    >>> config.user = purchase_user.id
    >>> return_ = Purchase()
    >>> return_.party = supplier
    >>> return_.payment_term = payment_term
    >>> return_.invoice_method = 'shipment'
    >>> return_line = PurchaseLine()
    >>> return_.lines.append(return_line)
    >>> return_line.product = product
    >>> return_line.quantity = -4.
    >>> return_line = PurchaseLine()
    >>> return_.lines.append(return_line)
    >>> return_line.type = 'comment'
    >>> return_line.description = 'Comment'
    >>> return_.click('quote')
    >>> return_.click('confirm')
    >>> return_.click('process')
    >>> return_.state
    u'processing'
    >>> return_.reload()
    >>> (len(return_.shipments), len(return_.shipment_returns),
    ...     len(return_.invoices))
    (0, 1, 0)

Check Return Shipments::

    >>> config.user = stock_user.id
    >>> ShipmentReturn = Model.get('stock.shipment.in.return')
    >>> ship_return, = return_.shipment_returns
    >>> ship_return.state
    u'waiting'
    >>> move_return, = ship_return.moves
    >>> move_return.product.rec_name
    u'product'
    >>> move_return.quantity
    4.0
    >>> ship_return.click('assign_try')
    True
    >>> ship_return.click('done')
    >>> ship_return.state
    u'done'
    >>> return_.reload()

Open supplier credit note::

    >>> config.user = purchase_user.id
    >>> credit_note, = return_.invoices
    >>> config.user = account_user.id
    >>> credit_note = Invoice(credit_note.id)
    >>> credit_note.type
    u'in'
    >>> len(credit_note.lines)
    1
    >>> sum(l.quantity for l in credit_note.lines)
    -4.0
    >>> credit_note.invoice_date = today
    >>> credit_note.click('post')

Mixing return and purchase::

    >>> config.user = purchase_user.id
    >>> mix = Purchase()
    >>> mix.party = supplier
    >>> mix.payment_term = payment_term
    >>> mix.invoice_method = 'order'
    >>> mixline = PurchaseLine()
    >>> mix.lines.append(mixline)
    >>> mixline.product = product
    >>> mixline.quantity = 7.
    >>> mixline_comment = PurchaseLine()
    >>> mix.lines.append(mixline_comment)
    >>> mixline_comment.type = 'comment'
    >>> mixline_comment.description = 'Comment'
    >>> mixline2 = PurchaseLine()
    >>> mix.lines.append(mixline2)
    >>> mixline2.product = product
    >>> mixline2.quantity = -2.
    >>> mix.click('quote')
    >>> mix.click('confirm')
    >>> mix.click('process')
    >>> mix.state
    u'processing'
    >>> mix.reload()
    >>> len(mix.moves), len(mix.shipment_returns), len(mix.invoices)
    (2, 1, 1)

Checking Shipments::

    >>> mix_return, = mix.shipment_returns
    >>> config.user = stock_user.id
    >>> mix_shipment = ShipmentIn()
    >>> mix_shipment.supplier = supplier
    >>> for move in mix.moves:
    ...     if move.id in [m.id for m in mix_return.moves]:
    ...         continue
    ...     incoming_move = Move(id=move.id)
    ...     mix_shipment.incoming_moves.append(incoming_move)
    >>> mix_shipment.click('receive')
    >>> mix_shipment.click('done')
    >>> mix.reload()
    >>> len(mix.shipments)
    1

    >>> mix_return.click('wait')
    >>> mix_return.click('assign_try')
    True
    >>> mix_return.click('done')
    >>> move_return, = mix_return.moves
    >>> move_return.product.rec_name
    u'product'
    >>> move_return.quantity
    2.0

Checking the invoice::

    >>> config.user = purchase_user.id
    >>> mix.reload()
    >>> mix_invoice, = mix.invoices
    >>> config.user = account_user.id
    >>> mix_invoice = Invoice(mix_invoice.id)
    >>> mix_invoice.type
    u'in'
    >>> len(mix_invoice.lines)
    3
    >>> sorted(l.quantity for l in mix_invoice.lines if l.quantity)
    [-2.0, 7.0]
    >>> mix_invoice.invoice_date = today
    >>> mix_invoice.click('post')

Mixing stuff with an invoice method 'on shipment'::

    >>> config.user = purchase_user.id
    >>> mix = Purchase()
    >>> mix.party = supplier
    >>> mix.payment_term = payment_term
    >>> mix.invoice_method = 'shipment'
    >>> mixline = PurchaseLine()
    >>> mix.lines.append(mixline)
    >>> mixline.product = product
    >>> mixline.quantity = 6.
    >>> mixline_comment = PurchaseLine()
    >>> mix.lines.append(mixline_comment)
    >>> mixline_comment.type = 'comment'
    >>> mixline_comment.description = 'Comment'
    >>> mixline2 = PurchaseLine()
    >>> mix.lines.append(mixline2)
    >>> mixline2.product = product
    >>> mixline2.quantity = -3.
    >>> mix.click('quote')
    >>> mix.click('confirm')
    >>> mix.click('process')
    >>> mix.state
    u'processing'
    >>> mix.reload()
    >>> len(mix.moves), len(mix.shipment_returns), len(mix.invoices)
    (2, 1, 0)

Checking Shipments::

    >>> config.user = stock_user.id
    >>> mix_return, = mix.shipment_returns
    >>> mix_shipment = ShipmentIn()
    >>> mix_shipment.supplier = supplier
    >>> for move in mix.moves:
    ...     if move.id in [m.id for m in mix_return.moves]:
    ...         continue
    ...     incoming_move = Move(id=move.id)
    ...     mix_shipment.incoming_moves.append(incoming_move)
    >>> mix_shipment.click('receive')
    >>> mix_shipment.click('done')
    >>> mix.reload()
    >>> len(mix.shipments)
    1

    >>> mix_return.click('wait')
    >>> mix_return.click('assign_try')
    True
    >>> mix_return.click('done')
    >>> move_return, = mix_return.moves
    >>> move_return.product.rec_name
    u'product'
    >>> move_return.quantity
    3.0

Purchase services::

    >>> config.user = purchase_user.id
    >>> service_purchase = Purchase()
    >>> service_purchase.party = supplier
    >>> service_purchase.payment_term = payment_term
    >>> purchase_line = service_purchase.lines.new()
    >>> purchase_line.product = service
    >>> purchase_line.quantity = 1
    >>> service_purchase.save()
    >>> service_purchase.click('quote')
    >>> service_purchase.click('confirm')
    >>> service_purchase.click('process')
    >>> service_purchase.state
    u'processing'
    >>> service_invoice, = service_purchase.invoices

Pay the service invoice::

    >>> config.user = account_user.id
    >>> service_invoice.invoice_date = today
    >>> service_invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [service_invoice])
    >>> pay.form.journal = cash_journal
    >>> pay.form.amount = service_invoice.total_amount
    >>> pay.execute('choice')
    >>> service_invoice.reload()
    >>> service_invoice.state
    u'paid'

Check service purchase states::

    >>> config.user = purchase_user.id
    >>> service_purchase.reload()
    >>> service_purchase.invoice_state
    u'paid'
    >>> service_purchase.shipment_state
    u'none'
    >>> service_purchase.state
    u'done'

Create a purchase to be invoiced on shipment partialy and check correctly
linked to invoices::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'shipment'
    >>> line = purchase.lines.new()
    >>> line.product = product
    >>> line.quantity = 10.0
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> config.user = stock_user.id
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> for move in purchase.moves:
    ...     incoming_move = Move(id=move.id)
    ...     incoming_move.quantity = 5.0
    ...     shipment.incoming_moves.append(incoming_move)
    >>> shipment.save()
    >>> for move in shipment.inventory_moves:
    ...     move.quantity = 5.0
    >>> shipment.click('receive')
    >>> shipment.click('done')
    >>> config.user = purchase_user.id
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.quantity
    5.0
    >>> stock_move, = invoice_line.stock_moves
    >>> stock_move.quantity
    5.0
    >>> stock_move.state
    u'done'
