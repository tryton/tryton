==========================
Analytic Purchase Scenario
==========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install analytic_purchase::

    >>> config = activate_modules('analytic_purchase')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create purchase user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_user.save()

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

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

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
    >>> template.purchasable = True
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

Purchase with analytic accounts::

    >>> config.user = purchase_user.id
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> entry, mandatory_entry = purchase_line.analytic_accounts
    >>> entry.root == root
    True
    >>> bool(entry.required)
    False
    >>> entry.account = analytic_account
    >>> mandatory_entry.root == mandatory_root
    True
    >>> bool(mandatory_entry.required)
    True
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5
    >>> mandatory_entry.account = mandatory_analytic_account
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')

Check invoice analytic accounts::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(purchase.invoices[0].id)
    >>> invoice_line, = invoice.lines
    >>> entry, mandatory_entry = invoice_line.analytic_accounts
    >>> entry.account == analytic_account
    True
    >>> mandatory_entry.account == mandatory_analytic_account
    True

Purchase with an empty analytic account::

    >>> config.user = purchase_user.id
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> entry, mandatory_entry = purchase_line.analytic_accounts
    >>> mandatory_entry.account = mandatory_analytic_account
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')

Check invoice analytic accounts::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(purchase.invoices[0].id)
    >>> invoice_line, = invoice.lines
    >>> entry, mandatory_entry = invoice_line.analytic_accounts
    >>> entry.account
    >>> mandatory_entry.account == mandatory_analytic_account
    True

Analytic entries are not required until quotation::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5
    >>> purchase.save()
    >>> purchase.click('quote')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...
    >>> purchase_line, = purchase.lines
    >>> entry, mandatory_entry = purchase_line.analytic_accounts
    >>> mandatory_entry.account = mandatory_analytic_account
    >>> purchase.click('quote')
