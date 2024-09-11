===================
Commission Scenario
===================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('commission_waiting', create_company, create_chart)

Get company::

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create waiting account::

    >>> Account = Model.get('account.account')
    >>> waiting_account = Account(name='Waiting Commission')
    >>> waiting_account.type = accounts['payable'].type
    >>> waiting_account.reconcile = True
    >>> waiting_account.deferral = True
    >>> waiting_account.party_required = False
    >>> waiting_account.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create commission product::

    >>> Uom = Model.get('product.uom')
    >>> Template = Model.get('product.template')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> template = Template()
    >>> template.name = 'Commission'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.account_category = account_category
    >>> template.save()
    >>> commission_product, = template.products

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
