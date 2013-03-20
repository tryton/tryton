==================================================
Purchase Shipment Cost with Account Stock Scenario
==================================================

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

Install purchase_shipment_cost::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ['purchase_shipment_cost',
    ...                 'account_stock_continental']),
    ...         ])
    >>> Module.install([x.id for x in modules], config.context)
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
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

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
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create category::

    >>> ProductCategory = Model.get('product.category')
    >>> category = ProductCategory(name='Category')
    >>> category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.category = category
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.account_stock = stock
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
    ...         config.context)[0])
    >>> template_average.cost_price_method = 'average'
    >>> template_average.save()
    >>> product_average = Product(Product.copy([product.id], {
    ...         'template': template_average.id,
    ...         }, config.context)[0])

    >>> carrier_product = Product()
    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.category = category
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.list_price = Decimal('5')
    >>> carrier_template.cost_price = Decimal('3')
    >>> carrier_template.account_expense = expense
    >>> carrier_template.account_revenue = revenue
    >>> carrier_template.save()
    >>> carrier_product.template = carrier_template
    >>> carrier_product.save()

Create carrier::

    >>> Carrier = Model.get('carrier')
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Receive a single product line::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> Location = Model.get('stock.location')
    >>> supplier_location, = Location.find([
    ...         ('code', '=', 'SUP'),
    ...         ])
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move = Move()
    >>> shipment.incoming_moves.append(move)
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 30
    >>> move.unit_price == Decimal('8')
    True
    >>> move = Move()
    >>> shipment.incoming_moves.append(move)
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product_average
    >>> move.quantity = 20
    >>> move.unit_price == Decimal('8')
    True
    >>> shipment.carrier = carrier
    >>> shipment.cost == Decimal('3')
    True
    >>> shipment.cost_currency == currency
    True
    >>> shipment.save()
    >>> ShipmentIn.receive([shipment.id], config.context)
    >>> shipment.reload()
    >>> shipment.state
    u'received'
    >>> move, move_average = shipment.incoming_moves
    >>> move.unit_price == Decimal('8.0600')
    True
    >>> move_average.unit_price == Decimal('8.0600')
    True
    >>> stock_supplier.reload()
    >>> (stock_supplier.debit, stock_supplier.credit) == \
    ...     (Decimal('0.00'), Decimal('398.20'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ...     (Decimal('0.00'), Decimal('3.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ...     (Decimal('401.20'), Decimal('0.00'))
    True

Receive many product lines::

    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> for quantity in (1, 3, 5):
    ...     move = Move()
    ...     shipment.incoming_moves.append(move)
    ...     move.from_location = supplier_location
    ...     move.to_location = shipment.warehouse.input_location
    ...     move.product = product
    ...     move.quantity = quantity
    >>> shipment.carrier = carrier
    >>> shipment.cost == Decimal('3')
    True
    >>> shipment.save()
    >>> ShipmentIn.receive([shipment.id], config.context)
    >>> shipment.reload()
    >>> shipment.state
    u'received'
    >>> [move.unit_price for move in shipment.incoming_moves] == \
    ...     [Decimal('8.3333'), Decimal('8.3333'), Decimal('8.3334')]
    True
    >>> stock_supplier.reload()
    >>> (stock_supplier.debit, stock_supplier.credit) == \
    ...     (Decimal('0.00'), Decimal('467.20'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ...     (Decimal('0.00'), Decimal('6.00'))
    True
    >>> stock.reload()
    >>> (stock.debit, stock.credit) == \
    ...     (Decimal('473.20'), Decimal('0.00'))
    True
