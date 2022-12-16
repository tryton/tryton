============================
Account Dunning Fee Scenario
============================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_dunning_fee')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> Journal = Model.get('account.journal')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_revenue.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create fees::

    >>> Fee = Model.get('account.dunning.fee')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template_fee = ProductTemplate(name='Fee')
    >>> template_fee.default_uom = unit
    >>> template_fee.type = 'service'
    >>> template_fee.list_price = Decimal('10')
    >>> template_fee.account_category = account_category
    >>> template_fee.save()
    >>> product_fee, = template_fee.products

    >>> fee = Fee(name='Fee')
    >>> fee.product = product_fee
    >>> fee.journal = journal_revenue
    >>> fee.compute_method = 'list_price'
    >>> fee.save()

    >>> fee_pc = Fee(name='Fee 15%')
    >>> fee_pc.product = product_fee
    >>> fee_pc.journal = journal_revenue
    >>> fee_pc.compute_method = 'percentage'
    >>> fee_pc.percentage = Decimal('.15')
    >>> fee_pc.save()

Create dunning procedure::

    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name='Procedure Fee')
    >>> level = procedure.levels.new()
    >>> level.overdue = datetime.timedelta(5)
    >>> level.fee = fee
    >>> level = procedure.levels.new()
    >>> level.overdue = datetime.timedelta(10)
    >>> level.fee = fee_pc
    >>> procedure.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.dunning_procedure = procedure
    >>> customer.save()

Create move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line  = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(100)
    >>> line.party = customer
    >>> line.maturity_date = period.start_date
    >>> move.save()

Check accounts::

    >>> receivable.reload()
    >>> receivable.balance
    Decimal('100.00')
    >>> revenue.reload()
    >>> revenue.balance
    Decimal('-100.00')

Create dunning on 5 days::

    >>> Dunning = Model.get('account.dunning')
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = (period.start_date
    ...     + datetime.timedelta(days=5))
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])

Process dunning::

    >>> process_dunning = Wizard('account.dunning.process',
    ...     [dunning])
    >>> process_dunning.execute('process')

Check accounts::

    >>> receivable.reload()
    >>> receivable.balance
    Decimal('110.00')
    >>> revenue.reload()
    >>> revenue.balance
    Decimal('-110.00')

Create dunning on 10 days::

    >>> Dunning = Model.get('account.dunning')
    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = (period.start_date
    ...     + datetime.timedelta(days=10))
    >>> create_dunning.execute('create_')
    >>> dunning, = Dunning.find([])

Process dunning::

    >>> process_dunning = Wizard('account.dunning.process',
    ...     [dunning])
    >>> process_dunning.execute('process')

Check accounts::

    >>> receivable.reload()
    >>> receivable.balance
    Decimal('125.00')
    >>> revenue.reload()
    >>> revenue.balance
    Decimal('-125.00')
