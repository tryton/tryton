================
Invoice Scenario
================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from.trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_invoice::

    >>> Module = Model.get('ir.module')
    >>> account_invoice_module, = Module.find(
    ...     [('name', '=', 'account_invoice')])
    >>> account_invoice_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']

Create tax::

    >>> tax = set_tax_code(create_tax(Decimal('.10')))
    >>> tax.save()
    >>> invoice_base_code = tax.invoice_base_code
    >>> invoice_tax_code = tax.invoice_tax_code
    >>> credit_note_base_code = tax.credit_note_base_code
    >>> credit_note_tax_code = tax.credit_note_tax_code

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('25')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='percent', percentage=Decimal(50))
    >>> delta = line.relativedeltas.new(days=20)
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
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'
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
    >>> invoice_base_code.reload()
    >>> invoice_base_code.sum
    Decimal('200.00')
    >>> invoice_tax_code.reload()
    >>> invoice_tax_code.sum
    Decimal('20.00')
    >>> credit_note_base_code.reload()
    >>> credit_note_base_code.sum
    Decimal('0.00')
    >>> credit_note_tax_code.reload()
    >>> credit_note_tax_code.sum
    Decimal('0.00')

Credit invoice with refund::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    u'paid'
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
    >>> invoice_base_code.reload()
    >>> invoice_base_code.sum
    Decimal('200.00')
    >>> invoice_tax_code.reload()
    >>> invoice_tax_code.sum
    Decimal('20.00')
    >>> credit_note_base_code.reload()
    >>> credit_note_base_code.sum
    Decimal('200.00')
    >>> credit_note_tax_code.reload()
    >>> credit_note_tax_code.sum
    Decimal('20.00')

Create empty invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.click('post')
    >>> invoice.state
    u'paid'
