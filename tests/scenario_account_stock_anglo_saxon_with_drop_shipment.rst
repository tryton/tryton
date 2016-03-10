=====================================================
Account Stock Anglo-Saxon with Drop Shipment Scenario
=====================================================

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

Install sale_supply, sale, purchase::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ('account_stock_anglo_saxon',
    ...             'sale_supply_drop_shipment', 'sale', 'purchase')),
    ...         ])
    >>> for module in modules:
    ...     module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create sale user::

    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_user.main_company = company
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

Create purchase user::

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_request_group, = Group.find(
    ...     [('name', '=', 'Purchase Request')])
    >>> purchase_user.groups.append(purchase_request_group)
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
    >>> ProductSupplier = Model.get('purchase.product_supplier')
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
    >>> template.supply_on_sale = True
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.product = template
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> product_supplier.lead_time = datetime.timedelta(0)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 50 products::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 50
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    u'processing'

Create Purchase from Request::

    >>> config.user = purchase_user.id
    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find()
    >>> purchase.payment_term = payment_term
    >>> purchase_line, = purchase.lines
    >>> purchase_line.unit_price = Decimal('3')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.state
    u'processing'
    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

Receive 50 products::

    >>> config.user = stock_user.id
    >>> shipment.click('ship')
    >>> shipment.click('done')
    >>> shipment.state
    u'done'
    >>> stock_supplier.reload()
    >>> stock_supplier.debit
    Decimal('0.00')
    >>> stock_supplier.credit
    Decimal('150.00')
    >>> stock_customer.reload()
    >>> stock_customer.debit
    Decimal('150.00')
    >>> stock_customer.credit
    Decimal('0.00')
    >>> stock.reload()
    >>> stock.debit
    Decimal('150.00')
    >>> stock.credit
    Decimal('150.00')

Open supplier invoice::

    >>> config.user = purchase_user.id
    >>> purchase.reload()
    >>> invoice, = purchase.invoices
    >>> config.user = account_user.id
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'
    >>> payable.reload()
    >>> payable.debit
    Decimal('0.00')
    >>> payable.credit
    Decimal('150.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('150.00')
    >>> expense.credit
    Decimal('150.00')
    >>> stock_supplier.reload()
    >>> stock_supplier.debit
    Decimal('150.00')
    >>> stock_supplier.credit
    Decimal('150.00')

Open customer invoice::

    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> config.user = account_user.id
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('500.00')
    >>> receivable.credit
    Decimal('0.00')
    >>> revenue.reload()
    >>> revenue.debit
    Decimal('0.00')
    >>> revenue.credit
    Decimal('500.00')
    >>> stock_customer.reload()
    >>> stock_customer.debit
    Decimal('150.00')
    >>> stock_customer.credit
    Decimal('150.00')
    >>> cogs.reload()
    >>> cogs.debit
    Decimal('150.00')
    >>> cogs.credit
    Decimal('0.00')
