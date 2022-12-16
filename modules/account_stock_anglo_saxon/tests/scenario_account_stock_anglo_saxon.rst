==================================
Account Stock Continental Scenario
==================================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> current_config = config.set_trytond()
    >>> current_config.pool.test = True

Install account_stock_continental, sale and purchase::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ('account_stock_anglo_saxon',
    ...             'sale', 'purchase')),
    ...     ])
    >>> Module.install([x.id for x in modules], current_config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='B2CK')
    >>> party.save()
    >>> company.party = party
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
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> current_config._context = User.get_preferences(True,
    ...     current_config.context)

Create an accountant user::

    >>> Group = Model.get('res.group')
    >>> accountant = User()
    >>> accountant.name = 'Accountant'
    >>> accountant.login = 'accountant'
    >>> accountant.password = 'accountant'
    >>> account_group, = Group.find([('name', '=', 'Account')])
    >>> accountant.groups.append(account_group)
    >>> accountant.save()

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name='%s' % today.year)
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_sequence = Sequence(name='%s' % today.year,
    ...     code='account.move',
    ...     company=company)
    >>> post_move_sequence.save()
    >>> fiscalyear.post_move_sequence = post_move_sequence
    >>> invoice_sequence = SequenceStrict(name='%s' % today.year,
    ...     code='account.invoice',
    ...     company=company)
    >>> invoice_sequence.save()
    >>> fiscalyear.out_invoice_sequence = invoice_sequence
    >>> fiscalyear.in_invoice_sequence = invoice_sequence
    >>> fiscalyear.out_credit_note_sequence = invoice_sequence
    >>> fiscalyear.in_credit_note_sequence = invoice_sequence
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], current_config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> AccountJournal = Model.get('account.journal')
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
    >>> (stock, stock_customer, stock_lost_found, stock_production,
    ...     stock_supplier) = Account.find([
    ...         ('kind', '=', 'stock'),
    ...         ('company', '=', company.id),
    ...         ('name', 'like', 'Stock%'),
    ...         ], order=[('name', 'ASC')])
    >>> cogs, = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', '=', 'COGS'),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> category = ProductCategory(name='Category')
    >>> category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.category = category
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.delivery_time = 0
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
    >>> template_average = ProductTemplate(ProductTemplate.copy([template.id],
    ...         current_config.context)[0])
    >>> template_average.cost_price_method = 'average'
    >>> template_average.save()
    >>> product_average = Product(Product.copy([product.id], {
    ...         'template': template_average.id,
    ...         }, current_config.context)[0])

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Purchase 12 products::

    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseLine = Model.get('purchase.line')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'shipment'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5.0
    >>> purchase_line.unit_price = Decimal(4)
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product_average
    >>> purchase_line.quantity = 7.0
    >>> purchase_line.unit_price = Decimal(6)
    >>> purchase.save()
    >>> Purchase.quote([purchase.id], current_config.context)
    >>> Purchase.confirm([purchase.id], current_config.context)
    >>> purchase.state
    u'confirmed'

Receive 9 products::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move = Move(purchase.moves[0].id)
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 4.0
    >>> move = Move(purchase.moves[1].id)
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 5.0
    >>> shipment.save()
    >>> ShipmentIn.receive([shipment.id], current_config.context)
    >>> ShipmentIn.done([shipment.id], current_config.context)
    >>> shipment.state
    u'done'
    >>> stock_supplier.reload()
    >>> stock.reload()
    >>> (stock_supplier.debit, stock_supplier.credit) == \
    ... (Decimal('0.00'), Decimal('46.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ... (Decimal('50.00'), Decimal('0.00'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ... (Decimal('0.00'), Decimal('4.00'))
    True

Open supplier invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice_line = invoice.lines[0]
    >>> invoice_line.unit_price = Decimal('6')
    >>> invoice_line = invoice.lines[1]
    >>> invoice_line.unit_price = Decimal('4')
    >>> invoice.invoice_date = today
    >>> invoice.save()
    >>> Invoice.post([invoice.id], current_config.context)
    >>> invoice.state
    u'posted'
    >>> payable.reload()
    >>> (payable.debit, payable.credit) == \
    ... (Decimal('0.00'), Decimal('44.00'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ... (Decimal('44.00'), Decimal('50.00'))
    True
    >>> stock_supplier.reload()
    >>> (stock_supplier.debit, stock_supplier.credit) == \
    ... (Decimal('46.00'), Decimal('46.00'))
    True

Sale 5 products::

    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product_average
    >>> sale_line.quantity = 3.0
    >>> sale.save()
    >>> Sale.quote([sale.id], current_config.context)
    >>> Sale.confirm([sale.id], current_config.context)
    >>> Sale.process([sale.id], current_config.context)
    >>> sale.state
    u'processing'

Send 5 products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> ShipmentOut.assign_try([shipment.id], current_config.context)
    True
    >>> shipment.state
    u'assigned'
    >>> shipment.reload()
    >>> ShipmentOut.pack([shipment.id], current_config.context)
    >>> shipment.state
    u'packed'
    >>> shipment.reload()
    >>> ShipmentOut.done([shipment.id], current_config.context)
    >>> shipment.state
    u'done'
    >>> stock_customer.reload()
    >>> (stock_customer.debit, stock_customer.credit) == \
    ... (Decimal('28.00'), Decimal('0.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ... (Decimal('50.00'), Decimal('28.00'))
    True

Open customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> Invoice.post([invoice.id], current_config.context)
    >>> invoice.state
    u'posted'
    >>> receivable.reload()
    >>> (receivable.debit, receivable.credit) == \
    ... (Decimal('50.00'), Decimal('0.00'))
    True
    >>> revenue.reload()
    >>> (revenue.debit, revenue.credit) == \
    ... (Decimal('0.00'), Decimal('50.00'))
    True
    >>> stock_customer.reload()
    >>> (stock_customer.debit, stock_customer.credit) == \
    ... (Decimal('28.00'), Decimal('28.00'))
    True
    >>> cogs.reload()
    >>> (cogs.debit, cogs.credit) == \
    ... (Decimal('28.00'), Decimal('0.00'))
    True

Now create a supplier invoice with an accountant::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5.0
    >>> purchase_line.unit_price = Decimal(4)
    >>> purchase.save()
    >>> Purchase.quote([purchase.id], current_config.context)
    >>> Purchase.confirm([purchase.id], current_config.context)
    >>> purchase.state
    u'confirmed'

    >>> new_config = config.set_trytond(user='accountant',
    ...     password='accountant', database_name=current_config.database_name)
    >>> for invoice in purchase.invoices:
    ...     invoice.invoice_date = today
    ...     invoice.save()
    >>> Invoice.validate_invoice([i.id for i in purchase.invoices], new_config.context)
