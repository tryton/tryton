=============
Sale Scenario
=============

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

Install sale::

    >>> Module = Model.get('ir.module.module')
    >>> sale_module, = Module.find([('name', '=', 'sale')])
    >>> Module.install([sale_module.id], config.context)
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
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> company.name = 'B2CK'
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

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
    >>> product.type = 'goods'
    >>> product.purchasable = True
    >>> product.salable = True
    >>> product.list_price = Decimal('10')
    >>> product.cost_price = Decimal('5')
    >>> product.cost_price_method = 'fixed'
    >>> product.account_expense = expense
    >>> product.account_revenue = revenue
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Create an Inventory::

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

Sale 5 products::

    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.type = 'comment'
    >>> sale_line.description = 'Comment'
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale.save()
    >>> Sale.quote([sale.id], config.context)
    >>> Sale.confirm([sale.id], config.context)
    >>> Sale.process([sale.id], config.context)
    >>> sale.state
    u'processing'
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 1)

Sale 5 products with an invoice method 'on shipment'::

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
    >>> sale_line.type = 'comment'
    >>> sale_line.description = 'Comment'
    >>> sale_line = SaleLine()
    >>> sale.lines.append(sale_line)
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale.save()
    >>> Sale.quote([sale.id], config.context)
    >>> Sale.confirm([sale.id], config.context)
    >>> Sale.process([sale.id], config.context)
    >>> sale.state
    u'processing'
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 0)

Validate Shipments::

    >>> sale.reload()
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> ShipmentOut.assign_try([shipment.id], config.context)
    True
    >>> ShipmentOut.pack([shipment.id], config.context)
    >>> ShipmentOut.done([shipment.id], config.context)

Open customer invoice::

    >>> sale.reload()
    >>> Invoice = Model.get('account.invoice')
    >>> invoice, = sale.invoices
    >>> invoice.type
    u'out_invoice'
    >>> len(invoice.lines)
    2
    >>> Invoice.open([invoice.id], config.context)
    >>> invoice.reload()
    >>> invoice.state
    u'open'
    >>> receivable.reload()
    >>> (receivable.debit, receivable.credit) == \
    ... (Decimal('50.00'), Decimal('0.00'))
    True
    >>> revenue.reload()
    >>> (revenue.debit, revenue.credit) == \
    ... (Decimal('0.00'), Decimal('50.00'))
    True

Create a Return::

    >>> return_ = Sale()
    >>> return_.party = customer
    >>> return_.payment_term = payment_term
    >>> return_.invoice_method = 'shipment'
    >>> return_line = SaleLine()
    >>> return_.lines.append(return_line)
    >>> return_line.product = product
    >>> return_line.quantity = -4.
    >>> return_line = SaleLine()
    >>> return_.lines.append(return_line)
    >>> return_line.type = 'comment'
    >>> return_line.description = 'Comment'
    >>> return_.save()
    >>> Sale.quote([return_.id], config.context)
    >>> Sale.confirm([return_.id], config.context)
    >>> Sale.process([return_.id], config.context)
    >>> return_.state
    u'processing'
    >>> return_.reload()
    >>> (len(return_.shipments), len(return_.shipment_returns),
    ...     len(return_.invoices))
    (0, 1, 0)

Check Return Shipments::

    >>> return_.reload()
    >>> ShipmentReturn = Model.get('stock.shipment.out.return')
    >>> ship_return, = return_.shipment_returns
    >>> ShipmentReturn.receive([ship_return.id], config.context)
    >>> move_return, = ship_return.incoming_moves
    >>> move_return.product.name
    u'product'
    >>> move_return.quantity
    4.0

Open customer credit note::

    >>> return_.reload()
    >>> credit_note, = return_.invoices
    >>> credit_note.type
    u'out_credit_note'
    >>> len(credit_note.lines)
    1
    >>> Invoice.open([credit_note.id], config.context)
    >>> credit_note.reload()
    >>> credit_note.state
    u'open'
    >>> receivable.reload()
    >>> (receivable.debit, receivable.credit) == (Decimal(50), Decimal(40))
    True
    >>> revenue.reload()
    >>> (revenue.debit, revenue.credit) == (Decimal(40), Decimal(50))
    True

Mixing return and sale::

    >>> mix = Sale()
    >>> mix.party = customer
    >>> mix.payment_term = payment_term
    >>> mix.invoice_method = 'order'
    >>> mixline = SaleLine()
    >>> mix.lines.append(mixline)
    >>> mixline.product = product
    >>> mixline.quantity = 7.
    >>> mixline_comment = SaleLine()
    >>> mix.lines.append(mixline_comment)
    >>> mixline_comment.type = 'comment'
    >>> mixline_comment.description = 'Comment'
    >>> mixline2 = SaleLine()
    >>> mix.lines.append(mixline2)
    >>> mixline2.product = product
    >>> mixline2.quantity = -2.
    >>> mix.save()
    >>> Sale.quote([mix.id], config.context)
    >>> Sale.confirm([mix.id], config.context)
    >>> Sale.process([mix.id], config.context)
    >>> mix.state
    u'processing'
    >>> mix.reload()
    >>> len(mix.shipments), len(mix.shipment_returns), len(mix.invoices)
    (1, 1, 2)

Checking Shipments::

    >>> mix.reload()
    >>> mix_returns, = mix.shipment_returns
    >>> mix_shipments, = mix.shipments
    >>> ShipmentReturn.receive([mix_returns.id], config.context)
    >>> move_return, = mix_returns.incoming_moves
    >>> move_return.product.name
    u'product'
    >>> move_return.quantity
    2.0
    >>> ShipmentOut.assign_try([mix_shipments.id], config.context)
    True
    >>> ShipmentOut.pack([mix_shipments.id], config.context)
    >>> ShipmentOut.done([mix_shipments.id], config.context)
    >>> move_shipment, = mix_shipments.outgoing_moves
    >>> move_shipment.product.name
    u'product'
    >>> move_shipment.quantity
    7.0

Checking the invoice::

    >>> mix.reload()
    >>> mix_invoice, mix_credit_note = sorted(mix.invoices,
    ...     key=attrgetter('type'), reverse=True)
    >>> mix_invoice.type, mix_credit_note.type
    (u'out_invoice', u'out_credit_note')
    >>> len(mix_invoice.lines), len(mix_credit_note.lines)
    (1, 1)
    >>> Invoice.open([mix_invoice.id], config.context)
    >>> mix_invoice.reload()
    >>> mix_invoice.state
    u'open'
    >>> Invoice.open([mix_credit_note.id], config.context)
    >>> mix_credit_note.reload()
    >>> mix_credit_note.state
    u'open'
    >>> receivable.reload()
    >>> (receivable.debit, receivable.credit) == (Decimal(120), Decimal(60))
    True
    >>> revenue.reload()
    >>> (revenue.debit, revenue.credit) == (Decimal(60), Decimal(120))
    True

Mixing stuff with an invoice method 'on shipment'::

    >>> mix = Sale()
    >>> mix.party = customer
    >>> mix.payment_term = payment_term
    >>> mix.invoice_method = 'shipment'
    >>> mixline = SaleLine()
    >>> mix.lines.append(mixline)
    >>> mixline.product = product
    >>> mixline.quantity = 6.
    >>> mixline_comment = SaleLine()
    >>> mix.lines.append(mixline_comment)
    >>> mixline_comment.type = 'comment'
    >>> mixline_comment.description = 'Comment'
    >>> mixline2 = SaleLine()
    >>> mix.lines.append(mixline2)
    >>> mixline2.product = product
    >>> mixline2.quantity = -3.
    >>> mix.save()
    >>> Sale.quote([mix.id], config.context)
    >>> Sale.confirm([mix.id], config.context)
    >>> Sale.process([mix.id], config.context)
    >>> mix.state
    u'processing'
    >>> mix.reload()
    >>> len(mix.shipments), len(mix.shipment_returns), len(mix.invoices)
    (1, 1, 0)

Checking Shipments::

    >>> mix.reload()
    >>> mix_returns, = mix.shipment_returns
    >>> mix_shipments, = mix.shipments
    >>> ShipmentReturn.receive([mix_returns.id], config.context)
    >>> move_return, = mix_returns.incoming_moves
    >>> move_return.product.name
    u'product'
    >>> move_return.quantity
    3.0
    >>> ShipmentOut.assign_try([mix_shipments.id], config.context)
    True
    >>> ShipmentOut.pack([mix_shipments.id], config.context)
    >>> move_shipment, = mix_shipments.outgoing_moves
    >>> move_shipment.product.name
    u'product'
    >>> move_shipment.quantity
    6.0
