=======================
Sale Complaint Scenario
=======================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale_complaint::

    >>> Module = Model.get('ir.module')
    >>> sale_module, = Module.find([('name', '=', 'sale_complaint')])
    >>> sale_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

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

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product.template = template
    >>> product.save()

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
    >>> sale.click('process')

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
    u'draft'
    >>> complaint.click('wait')
    >>> complaint.state
    u'waiting'
    >>> complaint.click('approve')
    >>> complaint.state
    u'approved'
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> return_sale = action.result
    >>> len(return_sale.lines)
    2
    >>> sum(l.quantity for l in return_sale.lines)
    -5.0

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
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
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
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    u'out'
    >>> len(credit_note.lines)
    2
    >>> sum(l.quantity for l in credit_note.lines)
    -5.0

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
    >>> complaint.click('process')
    >>> complaint.state
    u'done'
    >>> action, = complaint.actions
    >>> credit_note = action.result
    >>> credit_note.type
    u'out'
    >>> credit_note_line, = credit_note.lines
    >>> credit_note_line.quantity
    -1.0
