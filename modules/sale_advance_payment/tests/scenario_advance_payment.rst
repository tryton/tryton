==============================
Sale Advance Payment Scenario
==============================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> from trytond.modules.sale_advance_payment.tests.tools import \
    ...     create_advance_payment_term
    >>> today = datetime.date.today()

Activate sale_advance_payment::

    >>> config = activate_modules(['sale_advance_payment', 'sale_supply'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal years::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today=today))
    >>> fiscalyear.click('create_period')
    >>> next_fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today=today + relativedelta(years=1)))
    >>> next_fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']

    >>> Account = Model.get('account.account')
    >>> advance_payment_account = Account(
    ...     name='Advance Payment',
    ...     type=payable.type,
    ...     kind='revenue',
    ...     company=company,
    ...     party_required=True,
    ...     reconcile=True,
    ...     )
    >>> advance_payment_account.save()

    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.save()
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = cash_journal
    >>> payment_method.credit_account = cash
    >>> payment_method.debit_account = cash
    >>> payment_method.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.delivery_time = 0
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line = inventory.lines.new()
    >>> inventory_line.product = product
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Create advance payment term preventing the creation of shipment::

    >>> advance_payment_term = create_advance_payment_term(
    ...     'Advance Payment', '0.1 * total_amount', advance_payment_account,
    ...     block_supply=True)
    >>> advance_payment_term.save()

Create a normal sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.save()
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

As usual an invoice and a shipment has been created::

    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.account == revenue
    True
    >>> invoice.total_amount
    Decimal('20.00')
    >>> len(sale.shipments)
    1

Create a sale with advance payment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> sale.advance_payment_term = advance_payment_term
    >>> sale.click('quote')
    >>> condition, = sale.advance_payment_conditions
    >>> condition.amount
    Decimal('10.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

The advance payment invoice has been created::

    >>> invoice, = sale.advance_payment_invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.account == advance_payment_account
    True
    >>> invoice.total_amount
    Decimal('10.00')

    >>> invoice.click('post')
    >>> sale.reload()
    >>> len(sale.invoices)
    0
    >>> len(sale.shipments)
    0

Let's pay the advance payment invoice::

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')

    >>> sale.reload()
    >>> sale.state
    'processing'
    >>> len(sale.invoices)
    1
    >>> len(sale.shipments)
    1

    >>> invoice, = sale.invoices
    >>> invoice.total_amount
    Decimal('90.00')
    >>> len(invoice.lines)
    2
    >>> il1, il2 = sorted([il for il in invoice.lines], 
    ...     key=lambda il: 1 if il.product else 0)
    >>> il1.account == advance_payment_account
    True
    >>> il1.unit_price
    Decimal('-10.00')
    >>> il2.product == product
    True
    >>> il2.unit_price
    Decimal('20.0000')
    >>> il2.quantity
    5.0

Create another advance payment term preventing the packing stage::

    >>> advance_payment_term_no_pack = create_advance_payment_term(
    ...     'Advance Payment (blocked packing)',
    ...     '0.1 * total_amount', advance_payment_account, block_shipping=True)
    >>> advance_payment_term_no_pack.save()

Create a sale with advance payment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 6
    >>> sale.advance_payment_term = advance_payment_term_no_pack
    >>> sale.click('quote')
    >>> condition, = sale.advance_payment_conditions
    >>> condition.amount
    Decimal('12.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

The shipment has been created::

    >>> shipment, = sale.shipments

Let's try to pack it::

    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pack')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Let's pay the advance payment invoice::

    >>> invoice, = sale.advance_payment_invoices
    >>> invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> sale.reload()
    >>> sale.state
    'processing'

Packing the shipment is now allowed::

    >>> shipment.click('pack')
    >>> shipment.reload()
    >>> shipment.state
    'packed'

In case the product is to be supplied on sale
---------------------------------------------

Create the product::

    >>> sos_template = ProductTemplate()
    >>> sos_template.name = 'Supply On Sale product'
    >>> sos_template.default_uom = unit
    >>> sos_template.type = 'goods'
    >>> sos_template.purchasable = True
    >>> sos_template.salable = True
    >>> sos_template.list_price = Decimal('10')
    >>> sos_template.account_category = account_category
    >>> sos_template.supply_on_sale = True
    >>> sos_template.save()
    >>> sos_product, = sos_template.products

Sell 10 of those products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = sos_product
    >>> sale_line.quantity = 10
    >>> sale.advance_payment_term = advance_payment_term
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

There is no purchase request created yet::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> PurchaseRequest.find()
    []

The advance payment invoice has been created, now pay it::

    >>> invoice, = sale.advance_payment_invoices
    >>> invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> sale.reload()
    >>> sale.state
    'processing'

There is now a purchase request of the desired quantity::

    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    10.0

Testing advance payment conditions exception handling
-----------------------------------------------------

Create a sale with this term::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> sale.advance_payment_term = advance_payment_term
    >>> sale.click('quote')
    >>> condition1, = sale.advance_payment_conditions
    >>> condition1.amount
    Decimal('10.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'

Let's cancel the advance invoice::

    >>> inv, = sale.advance_payment_invoices
    >>> inv.click('cancel')
    >>> sale.reload()
    >>> sale.invoice_state
    'exception'

Handle the exception on the sale level, not recreating the invoice will create
the final invoice with the remaining total::

    >>> handle_exception = Wizard('sale.handle.invoice.exception', [sale])
    >>> _ = handle_exception.form.recreate_invoices.pop()
    >>> handle_exception.execute('handle')

    >>> sale.reload()
    >>> len(sale.advance_payment_invoices)
    1
    >>> last_invoice, = sale.invoices
    >>> last_invoice.total_amount
    Decimal('100.00')

Let's now use the same scenario but recreating the invoice instead of ignoring
it::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> sale.advance_payment_term = advance_payment_term
    >>> sale.save()
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> inv, = sale.advance_payment_invoices
    >>> inv.click('cancel')
    >>> sale.reload()
    >>> sale.invoice_state
    'exception'

    >>> handle_exception = Wizard('sale.handle.invoice.exception', [sale])
    >>> handle_exception.execute('handle')
    >>> sale.reload()
    >>> _, inv_recreated = sale.advance_payment_invoices
    >>> inv_recreated.total_amount
    Decimal('10.00')

    >>> inv_recreated.click('post')
    >>> pay = Wizard('account.invoice.pay', [inv_recreated])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> sale.reload()
    >>> last_invoice, = sale.invoices
    >>> last_invoice.total_amount
    Decimal('90.00')
