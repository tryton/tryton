=========================
Invoice Supplier Scenario
=========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, create_tax, create_tax_code, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')
    >>> period_ids = [p.id for p in fiscalyear.periods]

Get accounts::

    >>> accounts = get_accounts()
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']

Create tax::

    >>> TaxCode = Model.get('account.tax.code')
    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> invoice_base_code = create_tax_code(tax, 'base', 'invoice')
    >>> invoice_base_code.save()
    >>> invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
    >>> invoice_tax_code.save()
    >>> credit_note_base_code = create_tax_code(tax, 'base', 'credit')
    >>> credit_note_base_code.save()
    >>> credit_note_tax_code = create_tax_code(tax, 'tax', 'credit')
    >>> credit_note_tax_code.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.supplier_taxes.append(tax)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='remainder')
    >>> payment_term.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> invoice.reference = 'FAC001'
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = expense
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(10)
    >>> invoice.untaxed_amount
    Decimal('110.00')
    >>> invoice.tax_amount
    Decimal('10.00')
    >>> invoice.total_amount
    Decimal('120.00')
    >>> invoice.save()
    >>> invoice.state
    'draft'
    >>> bool(invoice.move)
    False
    >>> invoice.click('validate_invoice')
    >>> invoice.state
    'validated'
    >>> bool(invoice.move)
    True
    >>> invoice.move.state
    'draft'
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> bool(invoice.move)
    True
    >>> invoice.move.state
    'posted'
    >>> invoice.untaxed_amount
    Decimal('110.00')
    >>> invoice.tax_amount
    Decimal('10.00')
    >>> invoice.total_amount
    Decimal('120.00')
    >>> payable.reload()
    >>> payable.debit
    Decimal('0.00')
    >>> payable.credit
    Decimal('120.00')
    >>> expense.reload()
    >>> expense.debit
    Decimal('110.00')
    >>> expense.credit
    Decimal('0.00')
    >>> account_tax.reload()
    >>> account_tax.debit
    Decimal('10.00')
    >>> account_tax.credit
    Decimal('0.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_base_code = TaxCode(invoice_base_code.id)
    ...     invoice_base_code.amount
    Decimal('100.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_tax_code = TaxCode(invoice_tax_code.id)
    ...     invoice_tax_code.amount
    Decimal('10.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_base_code = TaxCode(credit_note_base_code.id)
    ...     credit_note_base_code.amount
    Decimal('0.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_tax_code = TaxCode(credit_note_tax_code.id)
    ...     credit_note_tax_code.amount
    Decimal('0.00')

Credit invoice::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = False
    >>> credit.execute('credit')
    >>> credit_note, = Invoice.find(
    ...     [('type', '=', 'in'), ('id', '!=', invoice.id)])
    >>> credit_note.state
    'draft'
    >>> credit_note.untaxed_amount
    Decimal('-110.00')
    >>> credit_note.tax_amount
    Decimal('-10.00')
    >>> credit_note.total_amount
    Decimal('-120.00')

A warning is raised when creating an invoice with same reference::

    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> invoice.reference = 'FAC001'
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    Traceback (most recent call last):
        ...
    InvoiceSimilarWarning: ...
    >>> invoice.reference = 'FAC002'
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Create a posted and a draft invoice to cancel::

    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('post')
    >>> invoice_draft, = Invoice.duplicate([invoice])

Cancel draft invoice::

    >>> invoice_draft.click('cancel')
    >>> invoice_draft.state
    'cancelled'
    >>> invoice_draft.move
    >>> invoice_draft.reconciled

Cancel posted invoice::

    >>> invoice.click('cancel')
    >>> invoice.state
    'cancelled'
    >>> invoice.cancel_move is not None
    True
    >>> bool(invoice.reconciled)
    True
