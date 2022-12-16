==============================================================
Purchase Shipment Cost with Account Stock Anglo-Saxon Scenario
==============================================================

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
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.account_stock_continental.tests.tools import \
    ...     add_stock_accounts
    >>> from trytond.modules.account_stock_anglo_saxon.tests.tools import \
    ...     add_cogs_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'purchase_shipment_cost',
    ...         'account_stock_anglo_saxon',
    ...         'purchase',
    ...         ])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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

    >>> AccountJournal = Model.get('account.journal')
    >>> stock_journal, = AccountJournal.find([('code', '=', 'STO')])

Create parties::

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
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'average'
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products

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

Create payment term::

    >>> payment_term = create_payment_term()
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
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.state
    'processing'

Receive 4 products::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move = Move(purchase.moves[0].id)
    >>> move.quantity = 4.0
    >>> shipment.incoming_moves.append(move)
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('3')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> move, = shipment.incoming_moves
    >>> move.unit_price
    Decimal('5.7500')
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> stock_in.reload()
    >>> stock.reload()
    >>> stock_in.debit
    Decimal('0.00')
    >>> stock_in.credit
    Decimal('20.00')
    >>> stock.reload()
    >>> stock.debit
    Decimal('23.00')
    >>> stock.credit
    Decimal('0.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('0.00')
    >>> expense.credit
    Decimal('3.00')

Open supplier invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> invoice.invoice_date = today
    >>> invoice.save()
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> payable.reload()
    >>> payable.debit
    Decimal('0.00')
    >>> payable.credit
    Decimal('20.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('20.00')
    >>> expense.credit
    Decimal('23.00')
    >>> stock_in.reload()
    >>> stock_in.debit
    Decimal('20.00')
    >>> stock_in.credit
    Decimal('20.00')
