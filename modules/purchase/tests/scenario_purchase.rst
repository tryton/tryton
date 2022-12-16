=================
Purchase Scenario
=================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install purchase::

    >>> Module = Model.get('ir.module.module')
    >>> purchase_module, = Module.find([('name', '=', 'purchase')])
    >>> Module.install([purchase_module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='B2CK')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

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

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', False)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

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
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create an Inventory::

    >>> config.user = stock_user.id
    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.save()
    >>> inventory_line = InventoryLine(product=product, inventory=inventory)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.save()
    >>> inventory_line.save()
    >>> Inventory.confirm([inventory.id], config.context)
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
    >>> purchase.save()
    >>> Purchase.quote([purchase.id], config.context)
    >>> Purchase.confirm([purchase.id], config.context)
    >>> purchase.state
    u'confirmed'
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
    >>> purchase.save()
    >>> Purchase.quote([purchase.id], config.context)
    >>> Purchase.confirm([purchase.id], config.context)
    >>> purchase.state
    u'confirmed'
    >>> purchase.reload()
    >>> len(purchase.moves), len(purchase.shipment_returns), len(purchase.invoices)
    (2, 0, 0)

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
    >>> ShipmentIn.receive([shipment.id], config.context)
    >>> ShipmentIn.done([shipment.id], config.context)
    >>> purchase.reload()
    >>> len(purchase.shipments), len(purchase.shipment_returns)
    (1, 0)

Open supplier invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice, = purchase.invoices
    >>> config.user = account_user.id
    >>> invoice.type
    u'in_invoice'
    >>> len(invoice.lines)
    2
    >>> invoice.invoice_date = today
    >>> invoice.save()
    >>> Invoice.post([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state
    u'posted'
    >>> payable.reload()
    >>> (payable.debit, payable.credit) == \
    ... (Decimal('0.00'), Decimal('25.00'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ... (Decimal('25.00'), Decimal('0.00'))
    True

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
    >>> return_.save()
    >>> Purchase.quote([return_.id], config.context)
    >>> Purchase.confirm([return_.id], config.context)
    >>> return_.state
    u'confirmed'
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
    >>> ShipmentReturn.assign_try([ship_return.id], config.context)
    True
    >>> ShipmentReturn.done([ship_return.id], config.context)
    >>> ship_return.reload()
    >>> ship_return.state
    u'done'
    >>> return_.reload()

Open supplier credit note::

    >>> credit_note, = return_.invoices
    >>> config.user = account_user.id
    >>> credit_note.type
    u'in_credit_note'
    >>> len(credit_note.lines)
    1
    >>> credit_note.invoice_date = today
    >>> credit_note.save()
    >>> Invoice.post([credit_note.id], config.context)
    >>> credit_note.reload()
    >>> credit_note.state
    u'posted'
    >>> payable.reload()
    >>> (payable.debit, payable.credit) == (Decimal(20), Decimal(25))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == (Decimal(25), Decimal(20))
    True

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
    >>> mix.save()
    >>> Purchase.quote([mix.id], config.context)
    >>> Purchase.confirm([mix.id], config.context)
    >>> mix.state
    u'confirmed'
    >>> mix.reload()
    >>> len(mix.moves), len(mix.shipment_returns), len(mix.invoices)
    (2, 1, 2)

Checking Shipments::

    >>> mix_returns, = mix.shipment_returns
    >>> config.user = stock_user.id
    >>> mix_shipments = ShipmentIn()
    >>> mix_shipments.supplier = supplier
    >>> for move in mix.moves:
    ...     if move.id in [m.id for m in mix_returns.moves]:
    ...         continue
    ...     incoming_move = Move(id=move.id)
    ...     mix_shipments.incoming_moves.append(incoming_move)
    >>> mix_shipments.save()
    >>> ShipmentIn.receive([mix_shipments.id], config.context)
    >>> ShipmentIn.done([mix_shipments.id], config.context)
    >>> mix.reload()
    >>> len(mix.shipments)
    1

    >>> ShipmentReturn.wait([mix_returns.id], config.context)
    >>> ShipmentReturn.assign_try([mix_returns.id], config.context)
    True
    >>> ShipmentReturn.done([mix_returns.id], config.context)
    >>> move_return, = mix_returns.moves
    >>> move_return.product.rec_name
    u'product'
    >>> move_return.quantity
    2.0

Checking the invoice::

    >>> config.user = purchase_user.id
    >>> mix.reload()
    >>> mix_invoice, mix_credit_note = sorted(mix.invoices,
    ...     key=attrgetter('type'), reverse=True)
    >>> config.user = account_user.id
    >>> mix_invoice.type, mix_credit_note.type
    (u'in_invoice', u'in_credit_note')
    >>> len(mix_invoice.lines), len(mix_credit_note.lines)
    (1, 1)
    >>> mix_invoice.invoice_date = today
    >>> mix_invoice.save()
    >>> Invoice.post([mix_invoice.id], config.context)
    >>> mix_invoice.reload()
    >>> mix_invoice.state
    u'posted'
    >>> mix_credit_note.invoice_date = today
    >>> mix_credit_note.save()
    >>> Invoice.post([mix_credit_note.id], config.context)
    >>> mix_credit_note.reload()
    >>> mix_credit_note.state
    u'posted'
    >>> payable.reload()
    >>> (payable.debit, payable.credit) == (Decimal(30), Decimal(60))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == (Decimal(60), Decimal(30))
    True

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
    >>> mix.save()
    >>> Purchase.quote([mix.id], config.context)
    >>> Purchase.confirm([mix.id], config.context)
    >>> mix.state
    u'confirmed'
    >>> mix.reload()
    >>> len(mix.moves), len(mix.shipment_returns), len(mix.invoices)
    (2, 1, 0)

Checking Shipments::

    >>> config.user = stock_user.id
    >>> mix_returns, = mix.shipment_returns
    >>> mix_shipments = ShipmentIn()
    >>> mix_shipments.supplier = supplier
    >>> for move in mix.moves:
    ...     if move.id in [m.id for m in mix_returns.moves]:
    ...         continue
    ...     incoming_move = Move(id=move.id)
    ...     mix_shipments.incoming_moves.append(incoming_move)
    >>> mix_shipments.save()
    >>> ShipmentIn.receive([mix_shipments.id], config.context)
    >>> ShipmentIn.done([mix_shipments.id], config.context)
    >>> mix.reload()
    >>> len(mix.shipments)
    1

    >>> ShipmentReturn.wait([mix_returns.id], config.context)
    >>> ShipmentReturn.assign_try([mix_returns.id], config.context)
    True
    >>> ShipmentReturn.done([mix_returns.id], config.context)
    >>> move_return, = mix_returns.moves
    >>> move_return.product.rec_name
    u'product'
    >>> move_return.quantity
    3.0
