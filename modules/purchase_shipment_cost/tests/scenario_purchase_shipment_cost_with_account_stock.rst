==================================================
Purchase Shipment Cost with Account Stock Scenario
==================================================

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
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.account_stock_continental.tests.tools import \
    ...     add_stock_accounts
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install purchase_shipment_cost::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ['purchase_shipment_cost',
    ...                 'account_stock_continental']),
    ...         ])
    >>> for module in modules:
    ...     module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.account_stock_method = 'continental'
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = add_stock_accounts(get_accounts(company), company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> stock = accounts['stock']
    >>> stock_customer = accounts['stock_customer']
    >>> stock_lost_found = accounts['stock_lost_found']
    >>> stock_production = accounts['stock_production']
    >>> stock_supplier = accounts['stock_supplier']

    >>> AccountJournal = Model.get('account.journal')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
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
    >>> template_average, = ProductTemplate.duplicate([template])
    >>> template_average.cost_price_method = 'average'
    >>> template_average.save()
    >>> product_average, = Product.duplicate([product], {
    ...         'template': template_average.id,
    ...         })

    >>> carrier_product = Product()
    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
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
    >>> move.unit_price
    Decimal('8')
    >>> move = Move()
    >>> shipment.incoming_moves.append(move)
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product_average
    >>> move.quantity = 20
    >>> move.unit_price
    Decimal('8')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.click('receive')
    >>> shipment.state
    u'received'
    >>> move, move_average = shipment.incoming_moves
    >>> move.unit_price
    Decimal('8.0600')
    >>> move_average.unit_price
    Decimal('8.0600')
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
    >>> shipment.cost
    Decimal('3')
    >>> shipment.click('receive')
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
