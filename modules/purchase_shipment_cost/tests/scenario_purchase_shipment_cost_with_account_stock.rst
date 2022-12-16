==================================================
Purchase Shipment Cost with Account Stock Scenario
==================================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.account_stock_continental.tests.tools import \
    ...     add_stock_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'purchase_shipment_cost',
    ...         'account_stock_continental',
    ...         ])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    >>> stock_in = accounts['stock_expense']
    >>> stock_out, = stock_in.duplicate()

    >>> AccountJournal = Model.get('account.journal')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.account_stock = stock
    >>> account_category.account_stock_in = stock_in
    >>> account_category.account_stock_out = stock_out
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> template.save()
    >>> product, = template.products
    >>> template_average, = template.duplicate({
    ...         'cost_price_method': 'average',
    ...         })
    >>> product_average, = template_average.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.list_price = Decimal('5')
    >>> carrier_template.account_category = account_category
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('3')
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

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
    >>> move.unit_price = Decimal('8')
    >>> move = Move()
    >>> shipment.incoming_moves.append(move)
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product_average
    >>> move.quantity = 20
    >>> move.unit_price = Decimal('8')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> move, move_average = shipment.incoming_moves
    >>> move.unit_price
    Decimal('8.0600')
    >>> move_average.unit_price
    Decimal('8.0600')
    >>> stock_in.reload()
    >>> (stock_in.debit, stock_in.credit) == \
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
    ...     move.unit_price = Decimal('8')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> [move.unit_price for move in shipment.incoming_moves] == \
    ...     [Decimal('8.3333'), Decimal('8.3333'), Decimal('8.3334')]
    True
    >>> stock_in.reload()
    >>> (stock_in.debit, stock_in.credit) == \
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
