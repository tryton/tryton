==========================
Analytic Purchase Scenario
==========================

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
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Activate modules::

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

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

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
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Purchase with analytic accounts::

    >>> set_user(purchase_user)
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> entry, = purchase_line.analytic_accounts
    >>> entry.root == root
    True
    >>> entry.account = analytic_account
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Check invoice analytic accounts::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(purchase.invoices[0].id)
    >>> invoice_line, = invoice.lines
    >>> entry, = invoice_line.analytic_accounts
    >>> entry.account == analytic_account
    True

Purchase with an empty analytic account::

    >>> set_user(purchase_user)
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> entry, = purchase_line.analytic_accounts
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Check invoice analytic accounts::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(purchase.invoices[0].id)
    >>> invoice_line, = invoice.lines
    >>> entry, = invoice_line.analytic_accounts
    >>> entry.account
