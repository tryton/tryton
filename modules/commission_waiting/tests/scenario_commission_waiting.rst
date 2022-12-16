===================
Commission Scenario
===================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install commission::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'commission_waiting'),
    ...         ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create waiting account::

    >>> Account = Model.get('account.account')
    >>> waiting_account = Account(name='Waiting Commission')
    >>> waiting_account.type = accounts['payable'].type
    >>> waiting_account.reconcile = True
    >>> waiting_account.deferral = True
    >>> waiting_account.party_required = False
    >>> waiting_account.kind = 'payable'
    >>> waiting_account.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create commission product::

    >>> Uom = Model.get('product.uom')
    >>> Template = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> commission_product = Product()
    >>> template = Template()
    >>> template.name = 'Commission'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.account_expense = accounts['expense']
    >>> template.account_revenue = accounts['revenue']
    >>> template.save()
    >>> commission_product.template = template
    >>> commission_product.save()

Create commission plan::

    >>> Plan = Model.get('commission.plan')
    >>> plan = Plan(name='Plan')
    >>> plan.commission_product = commission_product
    >>> plan.commission_method = 'payment'
    >>> line = plan.lines.new()
    >>> line.formula = 'amount * 0.1'
    >>> plan.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create agent::

    >>> Agent = Model.get('commission.agent')
    >>> agent_party = Party(name='Agent')
    >>> agent_party.supplier_payment_term = payment_term
    >>> agent_party.save()
    >>> agent = Agent(party=agent_party)
    >>> agent.type_ = 'agent'
    >>> agent.plan = plan
    >>> agent.currency = company.currency
    >>> agent.waiting_account = waiting_account
    >>> agent.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> invoice.payment_term = payment_term
    >>> invoice.agent = agent
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.description = 'Test'
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100.00')
    >>> invoice.save()

Post invoice::

    >>> invoice.click('post')
    >>> line, = invoice.lines
    >>> commission, = line.commissions
    >>> bool(commission.waiting_move)
    True
    >>> waiting_account.reload()
    >>> waiting_account.balance
    Decimal('-10.00')
    >>> accounts['payable'].reload()
    >>> accounts['payable'].balance
    Decimal('0.00')
    >>> accounts['expense'].reload()
    >>> accounts['expense'].balance
    Decimal('10.00')

Create commission invoices::

    >>> create_invoice = Wizard('commission.create_invoice')
    >>> create_invoice.form.from_ = None
    >>> create_invoice.form.to = None
    >>> create_invoice.execute('create_')

    >>> invoice, = Invoice.find([('state', '=', 'draft')])
    >>> invoice.invoice_date = today
    >>> invoice.click('post')

    >>> waiting_account.reload()
    >>> waiting_account.balance
    Decimal('0.00')
    >>> accounts['payable'].reload()
    >>> accounts['payable'].balance
    Decimal('-10.00')
    >>> accounts['expense'].reload()
    >>> accounts['expense'].balance
    Decimal('10.00')
