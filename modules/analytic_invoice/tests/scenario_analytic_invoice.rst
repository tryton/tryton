=========================
Analytic Invoice Scenario
=========================

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
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install analytic_invoice::

    >>> config = activate_modules('analytic_invoice')

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

Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()
    >>> mandatory_root = AnalyticAccount(type='root', name='Root',
    ...     mandatory=True)
    >>> mandatory_root.save()
    >>> mandatory_analytic_account = AnalyticAccount(root=mandatory_root,
    ...     parent=mandatory_root, name='Mandatory Analytic')
    >>> mandatory_analytic_account.save()

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
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create invoice with analytic accounts::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> entry, mandatory_entry = line.analytic_accounts
    >>> entry.root == root
    True
    >>> bool(entry.required)
    False
    >>> entry.account = analytic_account
    >>> mandatory_entry.root == mandatory_root
    True
    >>> bool(mandatory_entry.required)
    True
    >>> mandatory_entry.account = mandatory_analytic_account
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('200.00')
    >>> analytic_account.debit
    Decimal('0.00')
    >>> mandatory_analytic_account.reload()
    >>> mandatory_analytic_account.credit
    Decimal('200.00')
    >>> mandatory_analytic_account.debit
    Decimal('0.00')


Create invoice with an empty analytic account::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> entry, mandatory_entry = line.analytic_accounts
    >>> mandatory_entry.account = mandatory_analytic_account
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('40')
    >>> invoice.click('post')
    >>> invoice.state
    u'posted'
    >>> analytic_account.reload()
    >>> analytic_account.credit
    Decimal('200.00')
    >>> analytic_account.debit
    Decimal('0.00')
    >>> mandatory_analytic_account.reload()
    >>> mandatory_analytic_account.credit
    Decimal('240.00')
    >>> mandatory_analytic_account.debit
    Decimal('0.00')

Credit invoice with refund::

    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.form.with_refund = True
    >>> credit.execute('credit')
    >>> invoice.reload()
    >>> invoice.state
    u'paid'
    >>> mandatory_analytic_account.reload()
    >>> mandatory_analytic_account.credit
    Decimal('240.00')
    >>> mandatory_analytic_account.debit
    Decimal('40.00')
