==============================
Sale Advance Payment Scenario
==============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.sale_advance_payment.tests.tools import (
    ...     add_advance_payment_accounts, create_advance_payment_term)
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> next_week = today + dt.timedelta(days=7)

Activate sale_advance_payment::

    >>> config = activate_modules(
    ...     ['sale_advance_payment', 'sale_supply'],
    ...     create_company, create_chart)

Create fiscal years::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=(today, next_week)))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = add_advance_payment_accounts(get_accounts())
    >>> revenue = accounts['revenue']
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']
    >>> advance_payment_account = accounts['advance_payment']

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
    >>> assertEqual(invoice_line.account, revenue)
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
    >>> assertEqual(invoice_line.account, advance_payment_account)
    >>> invoice.total_amount
    Decimal('10.00')
    >>> assertEqual(invoice.invoice_date, next_week)
    >>> invoice.invoice_date = None
    >>> invoice.click('post')
    >>> sale.reload()
    >>> len(sale.invoices)
    0
    >>> len(sale.shipments)
    0

Let's pay the advance payment invoice::

    >>> pay = invoice.click('pay')
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
    >>> assertEqual(il1.account, advance_payment_account)
    >>> il1.unit_price
    Decimal('10.00')
    >>> assertEqual(il1.taxes_date, today)
    >>> il1.quantity
    -1.0
    >>> assertEqual(il2.product, product)
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
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    Traceback (most recent call last):
        ...
    ShippingBlocked: ...

Let's pay the advance payment invoice::

    >>> invoice, = sale.advance_payment_invoices
    >>> assertEqual(invoice.invoice_date, next_week)
    >>> invoice.invoice_date = None
    >>> invoice.click('post')
    >>> pay = invoice.click('pay')
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
    >>> sos_template.supply_on_sale = 'always'
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
    >>> assertEqual(invoice.invoice_date, next_week)
    >>> invoice.invoice_date = None
    >>> invoice.click('post')
    >>> pay = invoice.click('pay')
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

    >>> handle_exception = sale.click('handle_invoice_exception')
    >>> handle_exception.form.ignore_invoices.extend(
    ...     handle_exception.form.ignore_invoices.find())
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

    >>> handle_exception = sale.click('handle_invoice_exception')
    >>> handle_exception.form.recreate_invoices.extend(
    ...     handle_exception.form.recreate_invoices.find())
    >>> handle_exception.execute('handle')
    >>> sale.reload()
    >>> _, inv_recreated = sale.advance_payment_invoices
    >>> inv_recreated.total_amount
    Decimal('10.00')
    >>> assertEqual(inv_recreated.invoice_date, next_week)
    >>> inv_recreated.invoice_date = None
    >>> inv_recreated.click('post')
    >>> pay = inv_recreated.click('pay')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> sale.reload()
    >>> last_invoice, = sale.invoices
    >>> last_invoice.total_amount
    Decimal('90.00')
