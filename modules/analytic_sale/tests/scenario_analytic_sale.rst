======================
Analytic Sale Scenario
======================

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

Install analytic sale::

    >>> config = activate_modules('analytic_sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create sale user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_user.main_company = company
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

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
    >>> customer = Party(name='Customer')
    >>> customer.save()

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

Sale with analytic accounts::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> entry, mandatory_entry = sale_line.analytic_accounts
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
    >>> sale_line.product = product
    >>> sale_line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Check analytic accounts on invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice(sale.invoices[0].id)
    >>> invoice_line, = invoice.lines
    >>> entry, mandatory_entry = invoice_line.analytic_accounts
    >>> entry.account == analytic_account
    True
    >>> mandatory_entry.account == mandatory_analytic_account
    True

Sale with an empty analytic account::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> entry, mandatory_entry = sale_line.analytic_accounts
    >>> mandatory_entry.account = mandatory_analytic_account
    >>> sale_line.product = product
    >>> sale_line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> invoice, = sale.invoices

Check invoice analytic accounts::

    >>> invoice_line, = invoice.lines
    >>> entry, mandatory_entry = invoice_line.analytic_accounts
    >>> entry.account
    >>> mandatory_entry.account == mandatory_analytic_account
    True

Return sales using the wizard::

    >>> config.user = sale_user.id
    >>> return_sale = Wizard('sale.return_sale', [sale])
    >>> return_sale.execute('return_')
    >>> returned_sale, = Sale.find([
    ...     ('state', '=', 'draft'),
    ...     ])
    >>> sale_line, = returned_sale.lines
    >>> entry, mandatory_entry = sale_line.analytic_accounts
    >>> entry.account
    >>> mandatory_entry.account == mandatory_analytic_account
    True
