=======================
Sale Complaint Scenario
=======================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term

Activate modules::

    >>> config = activate_modules('sale_complaint')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create complaint type::

    >>> Type = Model.get('sale.complaint.type')
    >>> IrModel = Model.get('ir.model')
    >>> sale_type = Type(name='Sale')
    >>> sale_type.origin, = IrModel.find([('model', '=', 'sale.sale')])
    >>> sale_type.save()
    >>> sale_line_type = Type(name='Sale Line')
    >>> sale_line_type.origin, = IrModel.find([('model', '=', 'sale.line')])
    >>> sale_line_type.save()
    >>> invoice_type = Type(name='Invoice')
    >>> invoice_type.origin, = IrModel.find(
    ...     [('model', '=', 'account.invoice')])
    >>> invoice_type.save()
    >>> invoice_line_type = Type(name='Invoice Line')
    >>> invoice_line_type.origin, = IrModel.find(
    ...     [('model', '=', 'account.invoice.line')])
    >>> invoice_line_type.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

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
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 5 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2
    >>> sale.click('quote')
    >>> sale.click('confirm')

Post the invoice::

    >>> invoice, = sale.invoices
    >>> invoice.click('post')

Create a complaint to return the sale::

    >>> Complaint = Model.get('sale.complaint')
    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = sale_type
    >>> complaint.origin = sale
    >>> action = complaint.actions.new()
    >>> action.action = 'sale_return'
    >>> complaint.save()
    >>> complaint.state
    'draft'
    >>> complaint.click('wait')
    >>> complaint.state
    'waiting'
    >>> complaint.click('approve')
    >>> complaint.state
    'done'
    >>> action, = complaint.actions
    >>> return_sale = action.result
    >>> len(return_sale.lines)
    2
    >>> sum(l.quantity for l in return_sale.lines)
    -5.0

Create a complaint to return partially the sale::

    >>> Complaint = Model.get('sale.complaint')
    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = sale_type
    >>> complaint.origin = sale
    >>> action = complaint.actions.new()
    >>> action.action = 'sale_return'
    >>> sale_line = action.sale_lines.new()
    >>> sale_line.line = sale.lines[0]
    >>> sale_line.quantity = 1
    >>> sale_line.unit_price = Decimal('5')
    >>> sale_line = action.sale_lines.new()
    >>> sale_line.line = sale.lines[1]
    >>> complaint.save()
    >>> complaint.state
    'draft'
    >>> complaint.click('wait')
    >>> complaint.state
    'waiting'
    >>> complaint.click('approve')
    >>> complaint.state
    'done'
    >>> action, = complaint.actions
    >>> return_sale = action.result
    >>> len(return_sale.lines)
    2
    >>> sum(l.quantity for l in return_sale.lines)
    -3.0
    >>> return_sale.total_amount
    Decimal('-25.00')

Create a complaint to return a sale line::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = sale_line_type
    >>> complaint.origin = sale.lines[0]
    >>> action = complaint.actions.new()
    >>> action.action = 'sale_return'
    >>> action.quantity = 1
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.state
    'done'
    >>> action, = complaint.actions
    >>> return_sale = action.result
    >>> return_line, = return_sale.lines
    >>> return_line.quantity
    -1.0

Create a complaint to credit the invoice::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = invoice_type
    >>> complaint.origin = invoice
    >>> action = complaint.actions.new()
    >>> action.action = 'credit_note'
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.state
    'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    'out'
    >>> len(credit_note.lines)
    2
    >>> sum(l.quantity for l in credit_note.lines)
    -5.0

Create a complaint to credit partially the invoice::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = invoice_type
    >>> complaint.origin = invoice
    >>> action = complaint.actions.new()
    >>> action.action = 'credit_note'
    >>> invoice_line = action.invoice_lines.new()
    >>> invoice_line.line = invoice.lines[0]
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('5')
    >>> invoice_line = action.invoice_lines.new()
    >>> invoice_line.line = invoice.lines[1]
    >>> invoice_line.quantity = 1
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.state
    'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    'out'
    >>> len(credit_note.lines)
    2
    >>> sum(l.quantity for l in credit_note.lines)
    -2.0
    >>> credit_note.total_amount
    Decimal('-15.00')

Create a complaint to credit a invoice line::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = invoice_line_type
    >>> complaint.origin = invoice.lines[0]
    >>> action = complaint.actions.new()
    >>> action.action = 'credit_note'
    >>> action.quantity = 1
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.state
    'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    'out'
    >>> credit_note_line, = credit_note.lines
    >>> credit_note_line.quantity
    -1.0
