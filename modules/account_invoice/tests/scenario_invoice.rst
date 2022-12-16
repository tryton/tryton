================
Invoice Scenario
================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> tax_identifier = company.party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'BE0897290877'
    >>> company.party.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]
    >>> period_ids = [p.id for p in fiscalyear.periods]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

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

Create payment method::

    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> Sequence = Model.get('ir.sequence')
    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = account_cash
    >>> payment_method.debit_account = account_cash
    >>> payment_method.save()

Create Write Off method::

    >>> WriteOff = Model.get('account.move.reconcile.write_off')
    >>> sequence_journal, = Sequence.find([('code', '=', 'account.journal')])
    >>> journal_writeoff = Journal(name='Write-Off', type='write-off',
    ...     sequence=sequence_journal)
    >>> journal_writeoff.save()
    >>> writeoff_method = WriteOff()
    >>> writeoff_method.name = 'Rate loss'
    >>> writeoff_method.journal = journal_writeoff
    >>> writeoff_method.credit_account = expense
    >>> writeoff_method.debit_account = expense
    >>> writeoff_method.save()

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
    >>> account_category.customer_taxes.append(tax)
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
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> delta, = line.relativedeltas
    >>> delta.days = 20
    >>> line = payment_term.lines.new(type='remainder')
    >>> delta = line.relativedeltas.new(days=40)
    >>> payment_term.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line.account = revenue
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(20)
    >>> invoice.untaxed_amount
    Decimal('220.00')
    >>> invoice.tax_amount
    Decimal('20.00')
    >>> invoice.total_amount
    Decimal('240.00')
    >>> invoice.save()

Test change tax::

    >>> tax_line, = invoice.taxes
    >>> tax_line.tax == tax
    True
    >>> tax_line.tax = None
    >>> tax_line.tax = tax

Post invoice::

    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.tax_identifier.code
    'BE0897290877'
    >>> invoice.untaxed_amount
    Decimal('220.00')
    >>> invoice.tax_amount
    Decimal('20.00')
    >>> invoice.total_amount
    Decimal('240.00')
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('240.00')
    >>> receivable.credit
    Decimal('0.00')
    >>> revenue.reload()
    >>> revenue.debit
    Decimal('0.00')
    >>> revenue.credit
    Decimal('220.00')
    >>> account_tax.reload()
    >>> account_tax.debit
    Decimal('0.00')
    >>> account_tax.credit
    Decimal('20.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_base_code = TaxCode(invoice_base_code.id)
    ...     invoice_base_code.amount
    Decimal('200.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_tax_code = TaxCode(invoice_tax_code.id)
    ...     invoice_tax_code.amount
    Decimal('20.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_base_code = TaxCode(credit_note_base_code.id)
    ...     credit_note_base_code.amount
    Decimal('0.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_tax_code = TaxCode(credit_note_tax_code.id)
    ...     credit_note_tax_code.amount
    Decimal('0.00')

Credit invoice with refund::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.form.invoice_date = invoice.invoice_date
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    'cancelled'
    >>> invoice.reconciled == today
    True
    >>> credit_note, = Invoice.find([
    ...     ('type', '=', 'out'), ('id', '!=', invoice.id)])
    >>> credit_note.state
    'paid'
    >>> all(line.taxes_date == today for line in credit_note.lines)
    True
    >>> receivable.reload()
    >>> receivable.debit
    Decimal('240.00')
    >>> receivable.credit
    Decimal('240.00')
    >>> revenue.reload()
    >>> revenue.debit
    Decimal('220.00')
    >>> revenue.credit
    Decimal('220.00')
    >>> account_tax.reload()
    >>> account_tax.debit
    Decimal('20.00')
    >>> account_tax.credit
    Decimal('20.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_base_code = TaxCode(invoice_base_code.id)
    ...     invoice_base_code.amount
    Decimal('200.00')
    >>> with config.set_context(periods=period_ids):
    ...     invoice_tax_code = TaxCode(invoice_tax_code.id)
    ...     invoice_tax_code.amount
    Decimal('20.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_base_code = TaxCode(credit_note_base_code.id)
    ...     credit_note_base_code.amount
    Decimal('200.00')
    >>> with config.set_context(periods=period_ids):
    ...     credit_note_tax_code = TaxCode(credit_note_tax_code.id)
    ...     credit_note_tax_code.amount
    Decimal('20.00')

Pay invoice::

    >>> invoice, = invoice.duplicate()
    >>> invoice.click('post')

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.amount
    Decimal('240.00')
    >>> pay.form.amount = Decimal('120.00')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> pay.state
    'end'

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.amount
    Decimal('120.00')
    >>> pay.form.amount = Decimal('20.00')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> pay.form.type = 'partial'
    >>> pay.form.amount
    Decimal('20.00')
    >>> len(pay.form.lines_to_pay)
    1
    >>> len(pay.form.payment_lines)
    0
    >>> len(pay.form.lines)
    1
    >>> pay.form.amount_writeoff
    Decimal('100.00')
    >>> pay.execute('pay')

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.amount
    Decimal('-20.00')
    >>> pay.form.amount = Decimal('99.00')
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> pay.form.type = 'writeoff'
    >>> pay.form.writeoff = writeoff_method
    >>> pay.form.amount
    Decimal('99.00')
    >>> len(pay.form.lines_to_pay)
    1
    >>> len(pay.form.payment_lines)
    1
    >>> len(pay.form.lines)
    1
    >>> pay.form.amount_writeoff
    Decimal('1.00')
    >>> pay.execute('pay')

    >>> invoice.state
    'paid'
    >>> sorted(l.credit for l in invoice.reconciliation_lines)
    [Decimal('1.00'), Decimal('20.00'), Decimal('99.00'), Decimal('120.00')]

Create empty invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.click('post')
    >>> invoice.state
    'paid'

Create some complex invoice and test its taxes base rounding::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('0.0035')
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('0.0035')
    >>> invoice.save()
    >>> invoice.untaxed_amount
    Decimal('0.00')
    >>> invoice.taxes[0].base == invoice.untaxed_amount
    True
    >>> found_invoice, = Invoice.find([('untaxed_amount', '=', Decimal(0))])
    >>> found_invoice.id == invoice.id
    True
    >>> found_invoice, = Invoice.find([('total_amount', '=', Decimal(0))])
    >>> found_invoice.id == invoice.id
    True

Clear company tax_identifier::

    >>> tax_identifier, = company.party.identifiers
    >>> tax_identifier.type = None
    >>> tax_identifier.save()

Create a paid invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> pay.state
    'end'
    >>> invoice.tax_identifier
    >>> invoice.state
    'paid'

The invoice is posted when the reconciliation is deleted::

    >>> invoice.payment_lines[0].reconciliation.delete()
    >>> invoice.reload()
    >>> invoice.state
    'posted'
    >>> invoice.tax_identifier

Credit invoice with non line lines::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> line = invoice.lines.new()
    >>> line.type = 'comment'
    >>> line.description = 'Comment'
    >>> invoice.click('post')
    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
