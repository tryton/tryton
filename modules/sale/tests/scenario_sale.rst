=============
Sale Scenario
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Set employee::

    >>> User = Model.get('res.user')
    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> user = User(config.user)
    >>> user.employees.append(employee)
    >>> user.employee = employee
    >>> user.save()
    >>> set_user(user.id)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

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

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

    >>> account_category_tax, = account_category.duplicate()
    >>> account_category_tax.customer_taxes.append(tax)
    >>> account_category_tax.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category_tax
    >>> template.save()
    >>> product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = Decimal('30')
    >>> template.account_category = account_category
    >>> template.save()
    >>> service, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

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
    >>> sale.click('quote')
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))
    >>> sale.quoted_by == employee
    True
    >>> sale.click('confirm')
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))
    >>> sale.confirmed_by == employee
    True
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'waiting'
    >>> sale.invoice_state
    'waiting'
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 1)
    >>> invoice, = sale.invoices
    >>> invoice.origins == sale.rec_name
    True
    >>> shipment, = sale.shipments
    >>> shipment.origins == sale.rec_name
    True

Invoice line must be linked to stock move::

    >>> _, invoice_line1, invoice_line2 = sorted(invoice.lines,
    ...     key=lambda l: l.quantity or 0)
    >>> stock_move1, stock_move2 = sorted(shipment.outgoing_moves,
    ...     key=lambda m: m.quantity or 0)
    >>> invoice_line1.stock_moves == [stock_move1]
    True
    >>> stock_move1.invoice_lines == [invoice_line1]
    True
    >>> invoice_line2.stock_moves == [stock_move2]
    True
    >>> stock_move2.invoice_lines == [invoice_line2]
    True

Check actual quantity::

    >>> all(l.quantity == l.actual_quantity for l in sale.lines)
    True

Post invoice and check no new invoices::


    >>> for invoice in sale.invoices:
    ...     invoice.click('post')
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 1)

Testing the report::

    >>> sale_report = Report('sale.sale')
    >>> ext, _, _, name = sale_report.execute([sale], {})
    >>> ext
    'odt'
    >>> name
    'Sale-1'

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
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'waiting'
    >>> sale.invoice_state
    'none'
    >>> sale.reload()
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 0)

Not yet linked to invoice lines::

    >>> shipment, = sale.shipments
    >>> stock_move1, stock_move2 = sorted(shipment.outgoing_moves,
    ...     key=lambda m: m.quantity or 0)
    >>> len(stock_move1.invoice_lines)
    0
    >>> len(stock_move2.invoice_lines)
    0

Validate Shipments::

    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')

Open customer invoice::

    >>> sale.reload()
    >>> sale.invoice_state
    'waiting'
    >>> invoice, = sale.invoices
    >>> invoice.type
    'out'
    >>> invoice_line1, invoice_line2 = sorted(invoice.lines,
    ...     key=lambda l: l.quantity or 0)
    >>> for line in invoice.lines:
    ...     line.quantity = 1
    ...     line.save()
    >>> invoice.click('post')

Invoice lines must be linked to each stock moves::

    >>> invoice_line1.stock_moves == [stock_move1]
    True
    >>> invoice_line2.stock_moves == [stock_move2]
    True

Check second invoices::

    >>> sale.reload()
    >>> len(sale.invoices)
    2
    >>> sum(l.quantity for i in sale.invoices for l in i.lines)
    5.0

Sale 5 products with shipment method 'on invoice'::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.shipment_method = 'invoice'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'none'
    >>> sale.invoice_state
    'waiting'
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (0, 0, 1)

Not yet linked to stock moves::

    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> len(invoice_line.stock_moves)
    0

Post and Pay Invoice for 4 products::

    >>> invoice_line, = invoice.lines
    >>> invoice_line.quantity
    5.0
    >>> invoice_line.quantity = 4.0
    >>> invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> invoice.reload()
    >>> invoice.state
    'paid'

Invoice lines linked to 1 move::

    >>> invoice_line, = invoice.lines
    >>> len(invoice_line.stock_moves)
    1

Stock moves must be linked to invoice line::

    >>> sale.reload()
    >>> shipment, = sale.shipments
    >>> shipment.reload()
    >>> stock_move, = shipment.outgoing_moves
    >>> stock_move.quantity
    4.0
    >>> stock_move.invoice_lines == [invoice_line]
    True

Ship 3 products::

    >>> stock_inventory_move, = shipment.inventory_moves
    >>> stock_inventory_move.quantity
    4.0
    >>> stock_inventory_move.quantity = 3.0
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

New shipments created::

    >>> sale.reload()
    >>> len(sale.shipments)
    2

Invoice lines linked to new moves::

    >>> invoice.reload()
    >>> invoice_line, = invoice.lines
    >>> len(invoice_line.stock_moves)
    2

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
    >>> return_.click('quote')
    >>> return_.click('confirm')
    >>> return_.state
    'processing'
    >>> return_.shipment_state
    'waiting'
    >>> return_.invoice_state
    'none'
    >>> (len(return_.shipments), len(return_.shipment_returns),
    ...     len(return_.invoices))
    (0, 1, 0)

Receive Return Shipment for 3 products::

    >>> ship_return, = return_.shipment_returns
    >>> move_return, = ship_return.incoming_moves
    >>> move_return.product.rec_name
    'product'
    >>> move_return.quantity
    4.0
    >>> move_return.quantity = 3
    >>> ship_return.click('receive')

Check Return::

    >>> return_.reload()
    >>> return_.shipment_state
    'waiting'
    >>> return_.invoice_state
    'waiting'
    >>> (len(return_.shipments), len(return_.shipment_returns),
    ...     len(return_.invoices))
    (0, 2, 1)

Open customer credit note::

    >>> credit_note, = return_.invoices
    >>> credit_note.type
    'out'
    >>> len(credit_note.lines)
    1
    >>> sum(l.quantity for l in credit_note.lines)
    -3.0
    >>> credit_note.click('post')

Receive Remaining Return Shipment::

    >>> return_.reload()
    >>> _, ship_return = return_.shipment_returns
    >>> move_return, = ship_return.incoming_moves
    >>> move_return.product.rec_name
    'product'
    >>> move_return.quantity
    1.0
    >>> ship_return.click('receive')

Check Return::

    >>> return_.reload()
    >>> return_.shipment_state
    'sent'
    >>> return_.invoice_state
    'waiting'
    >>> (len(return_.shipments), len(return_.shipment_returns),
    ...     len(return_.invoices))
    (0, 2, 2)

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
    >>> mix.click('quote')
    >>> mix.click('confirm')
    >>> mix.state
    'processing'
    >>> mix.shipment_state
    'waiting'
    >>> mix.invoice_state
    'waiting'
    >>> len(mix.shipments), len(mix.shipment_returns), len(mix.invoices)
    (1, 1, 1)

Checking Shipments::

    >>> mix_return, = mix.shipment_returns
    >>> mix_shipment, = mix.shipments
    >>> mix_return.click('receive')
    >>> move_return, = mix_return.incoming_moves
    >>> move_return.product.rec_name
    'product'
    >>> move_return.quantity
    2.0
    >>> mix_shipment.click('assign_try')
    True
    >>> mix_shipment.click('pick')
    >>> mix_shipment.click('pack')
    >>> mix_shipment.click('done')
    >>> move_shipment, = mix_shipment.outgoing_moves
    >>> move_shipment.product.rec_name
    'product'
    >>> move_shipment.quantity
    7.0

Checking the invoice::

    >>> mix.reload()
    >>> mix_invoice, = mix.invoices
    >>> mix_invoice.type
    'out'
    >>> len(mix_invoice.lines)
    3
    >>> sorted(l.quantity for l in mix_invoice.lines if l.quantity)
    [-2.0, 7.0]
    >>> mix_invoice.click('post')

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
    >>> mix.click('quote')
    >>> mix.click('confirm')
    >>> mix.state
    'processing'
    >>> mix.shipment_state
    'waiting'
    >>> mix.invoice_state
    'none'
    >>> len(mix.shipments), len(mix.shipment_returns), len(mix.invoices)
    (1, 1, 0)

Checking Shipments::

    >>> mix_return, = mix.shipment_returns
    >>> mix_shipment, = mix.shipments
    >>> mix_return.click('receive')
    >>> move_return, = mix_return.incoming_moves
    >>> move_return.product.rec_name
    'product'
    >>> move_return.quantity
    3.0
    >>> mix_shipment.click('assign_try')
    True
    >>> mix_shipment.click('pick')
    >>> mix_shipment.click('pack')
    >>> move_shipment, = mix_shipment.outgoing_moves
    >>> move_shipment.product.rec_name
    'product'
    >>> move_shipment.quantity
    6.0

Sale services::

    >>> service_sale = Sale()
    >>> service_sale.party = customer
    >>> service_sale.payment_term = payment_term
    >>> sale_line = service_sale.lines.new()
    >>> sale_line.product = service
    >>> sale_line.quantity = 1
    >>> service_sale.save()
    >>> service_sale.click('quote')
    >>> service_sale.click('confirm')
    >>> service_sale.state
    'processing'
    >>> service_sale.shipment_state
    'none'
    >>> service_sale.invoice_state
    'waiting'
    >>> service_invoice, = service_sale.invoices

Pay the service invoice::

    >>> service_invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [service_invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> service_invoice.reload()
    >>> service_invoice.state
    'paid'

Check service sale states::

    >>> service_sale.reload()
    >>> service_sale.invoice_state
    'paid'
    >>> service_sale.shipment_state
    'none'
    >>> service_sale.state
    'done'

Return sales using the wizard::

    >>> sale_to_return = Sale()
    >>> sale_to_return.party = customer
    >>> sale_to_return.payment_term = payment_term
    >>> sale_line = sale_to_return.lines.new()
    >>> sale_line.product = service
    >>> sale_line.quantity = 1
    >>> sale_line = sale_to_return.lines.new()
    >>> sale_line.type = 'comment'
    >>> sale_line.description = 'Test comment'
    >>> sale_to_return.click('quote')
    >>> sale_to_return.click('confirm')
    >>> sale_to_return.state
    'processing'
    >>> return_sale = Wizard('sale.return_sale', [sale_to_return])
    >>> return_sale.execute('return_')
    >>> returned_sale, = Sale.find([
    ...     ('state', '=', 'draft'),
    ...     ])
    >>> returned_sale.origin == sale_to_return
    True
    >>> sorted([x.quantity or 0 for x in returned_sale.lines])
    [-1.0, 0]

Create a sale to be invoiced on shipment partialy and check correctly linked
to invoices::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> shipment, = sale.shipments
    >>> for move in shipment.inventory_moves:
    ...     move.quantity = 5.0
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.quantity
    5.0
    >>> stock_move, = invoice_line.stock_moves
    >>> stock_move.quantity
    5.0
    >>> stock_move.state
    'done'

Create a sale to be sent on invoice partially and check correctly linked to
invoices::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.shipment_method = 'invoice'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.stock_moves == []
    True
    >>> invoice_line.quantity = 5.0
    >>> invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> invoice.reload()
    >>> invoice.state
    'paid'
    >>> invoice_line.reload()
    >>> stock_move, = invoice_line.stock_moves
    >>> stock_move.quantity
    5.0
    >>> stock_move.state
    'draft'

Deleting a line from a invoice should recreate it::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> invoice, = sale.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice.lines.remove(invoice_line)
    >>> invoice.click('post')
    >>> sale.reload()
    >>> new_invoice, = sale.invoices
    >>> new_invoice.number
    >>> len(new_invoice.lines)
    1
