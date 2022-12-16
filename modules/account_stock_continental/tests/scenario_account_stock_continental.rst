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

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_stock_continental, sale and purchase::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ('account_stock_continental',
    ...             'sale', 'purchase')),
    ...     ])
    >>> Module.button_install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('start')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> company.name = 'B2CK'
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
    >>> config._context = User.get_preferences(True, config.context)

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
    >>> FiscalYear.create_period([fiscalyear.id], config.context)
    True

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> AccountJournal = Model.get('account.journal')
    >>> account_template, = AccountTemplate.find([('parent', '=', False)])
    >>> create_chart_account = Wizard('account.account.create_chart_account')
    >>> create_chart_account.execute('account')
    >>> create_chart_account.form.account_template = account_template
    >>> create_chart_account.form.company = company
    >>> create_chart_account.execute('create_account')
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
    >>> stock, stock_supplier, stock_lost_found, stock_customer = Account.find([
    ...         ('kind', '=', 'other'),
    ...         ('company', '=', company.id),
    ...         ('name', 'like', 'Stock%'),
    ...         ], order=[('name', 'ASC')])
    >>> create_chart_account.form.account_receivable = receivable
    >>> create_chart_account.form.account_payable = payable
    >>> create_chart_account.execute('create_properties')
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
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> product.name = 'product'
    >>> product.category = category
    >>> product.default_uom = unit
    >>> product.type = 'stockable'
    >>> product.purchasable = True
    >>> product.salable = True
    >>> product.list_price = Decimal('10')
    >>> product.cost_price = Decimal('5')
    >>> product.account_expense = expense
    >>> product.account_revenue = revenue
    >>> product.account_stock = stock
    >>> product.account_stock_supplier = stock_supplier
    >>> product.account_stock_customer = stock_customer
    >>> product.account_stock_lost_found = stock_lost_found
    >>> product.account_journal_stock_supplier = stock_journal
    >>> product.account_journal_stock_customer = stock_journal
    >>> product.account_journal_stock_lost_found = stock_journal
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder')
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Purchase 5 products::

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
    >>> purchase.save()
    >>> Purchase.workflow_trigger_validate(purchase.id, 'quotation',
    ...     config.context)
    >>> Purchase.workflow_trigger_validate(purchase.id, 'confirm',
    ...     config.context)
    >>> purchase.state
    u'confirmed'

Receive 4 products::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move = Move(purchase.moves[0].id)
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 4.0
    >>> shipment.save()
    >>> ShipmentIn.workflow_trigger_validate(shipment.id, 'received',
    ...     config.context)
    >>> ShipmentIn.workflow_trigger_validate(shipment.id, 'done',
    ...     config.context)
    >>> shipment.state
    u'done'
    >>> stock_supplier.reload()
    >>> (stock_supplier.debit, stock_supplier.credit) == \
    ... (Decimal('0.00'), Decimal('20.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ... (Decimal('20.00'), Decimal('0.00'))
    True

Open supplier invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.unit_price = Decimal('6')
    >>> invoice.save()
    >>> Invoice.workflow_trigger_validate(invoice.id, 'open', config.context)
    >>> invoice.state
    u'open'
    >>> payable.reload()
    >>> (payable.debit, payable.credit) == \
    ... (Decimal('0.00'), Decimal('24.00'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ... (Decimal('24.00'), Decimal('0.00'))
    True

Update cost price of product::

    >>> product.cost_price = Decimal('6')
    >>> product.save()

Sale 2 products::

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
    >>> sale.save()
    >>> Sale.workflow_trigger_validate(sale.id, 'quotation', config.context)
    >>> Sale.workflow_trigger_validate(sale.id, 'confirm', config.context)
    >>> sale.state
    u'confirmed'

Send 2 products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> ShipmentOut.workflow_trigger_validate(shipment.id, 'assign',
    ...     config.context)
    >>> shipment.state
    u'assigned'
    >>> shipment.reload()
    >>> ShipmentOut.workflow_trigger_validate(shipment.id, 'packed',
    ...     config.context)
    >>> shipment.state
    u'packed'
    >>> shipment.reload()
    >>> ShipmentOut.workflow_trigger_validate(shipment.id, 'done',
    ...     config.context)
    >>> shipment.state
    u'done'
    >>> stock_customer.reload()
    >>> (stock_customer.debit, stock_customer.credit) == \
    ... (Decimal('12.00'), Decimal('0.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ... (Decimal('20.00'), Decimal('12.00'))
    True

Open customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> Invoice.workflow_trigger_validate(invoice.id, 'open', config.context)
    >>> invoice.state
    u'open'
    >>> receivable.reload()
    >>> (receivable.debit, receivable.credit) == \
    ... (Decimal('20.00'), Decimal('0.00'))
    True
    >>> revenue.reload()
    >>> (revenue.debit, revenue.credit) == \
    ... (Decimal('0.00'), Decimal('20.00'))
    True

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.save()
    >>> complete_inventory = Wizard('stock.inventory.complete', [inventory])
    >>> inventory_line, = inventory.lines
    >>> inventory_line.quantity = 1.0
    >>> inventory.save()
    >>> Inventory.workflow_trigger_validate(inventory.id, 'done', config.context)
    >>> inventory.state
    u'done'
    >>> stock_lost_found.reload()
    >>> (stock_lost_found.debit, stock_lost_found.credit) == \
    ... (Decimal('6.00'), Decimal('0.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ... (Decimal('20.00'), Decimal('18.00'))
    True
