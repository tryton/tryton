======================
Account Asset Scenario
======================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_asset::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...     ('name', '=', 'account_asset'),
    ... ])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.', mon_thousands_sep=',')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name='%s' % today.year)
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_sequence = Sequence(name='%s' % today.year,
    ...     code='account.move',
    ...     company=company)
    >>> post_move_sequence.save()
    >>> fiscalyear.post_move_sequence = post_move_sequence
    >>> invoice_sequence = SequenceStrict(name='%s' % today.year,
    ...     code='account.invoice',
    ...     company=company)
    >>> invoice_sequence.save()
    >>> fiscalyear.out_invoice_sequence = invoice_sequence
    >>> fiscalyear.in_invoice_sequence = invoice_sequence
    >>> fiscalyear.out_credit_note_sequence = invoice_sequence
    >>> fiscalyear.in_credit_note_sequence = invoice_sequence
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> AccountJournal = Model.get('account.journal')
    >>> account_template, = AccountTemplate.find([('parent', '=', False)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...     ('kind', '=', 'receivable'),
    ...     ('company', '=', company.id),
    ... ])
    >>> payable, = Account.find([
    ...     ('kind', '=', 'payable'),
    ...     ('company', '=', company.id),
    ... ])
    >>> revenue, = Account.find([
    ...     ('kind', '=', 'revenue'),
    ...     ('company', '=', company.id),
    ... ])
    >>> asset_account, expense = Account.find([
    ...     ('kind', '=', 'expense'),
    ...     ('company', '=', company.id),
    ... ], order=[('name', 'DESC')])
    >>> depreciation_account, = Account.find([
    ...     ('kind', '=', 'other'),
    ...     ('name', '=', 'Depreciation'),
    ... ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create an asset::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> asset_product = Product()
    >>> asset_template = ProductTemplate()
    >>> asset_template.name = 'Asset'
    >>> asset_template.type = 'assets'
    >>> asset_template.default_uom = unit
    >>> asset_template.list_price = Decimal('1000')
    >>> asset_template.cost_price = Decimal('1000')
    >>> asset_template.depreciable = True
    >>> asset_template.account_expense = expense
    >>> asset_template.account_revenue = revenue
    >>> asset_template.account_asset = asset_account
    >>> asset_template.account_depreciation = depreciation_account
    >>> asset_template.depreciation_duration = Decimal(24)
    >>> asset_template.save()
    >>> asset_product.template = asset_template
    >>> asset_product.save()

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm(name='Direct')
    >>> payment_term_line = PaymentTermLine(type='remainder', days=0)
    >>> payment_term.lines.append(payment_term_line)
    >>> payment_term.save()

Buy an asset::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> supplier_invoice = Invoice(type='in_invoice')
    >>> supplier_invoice.party = supplier
    >>> invoice_line = InvoiceLine()
    >>> supplier_invoice.lines.append(invoice_line)
    >>> invoice_line.product = asset_product
    >>> invoice_line.quantity = 1
    >>> invoice_line.account == asset_account
    True
    >>> supplier_invoice.invoice_date = today + relativedelta(day=1, month=1)
    >>> supplier_invoice.save()
    >>> Invoice.post([supplier_invoice.id], config.context)
    >>> supplier_invoice.state
    u'posted'
    >>> invoice_line, = supplier_invoice.lines
    >>> (asset_account.debit, asset_account.credit) == \
    ...     (Decimal('1000'), Decimal('0'))
    True

Depreciate the asset::

    >>> Asset = Model.get('account.asset')
    >>> asset = Asset()
    >>> asset.product = asset_product
    >>> asset.supplier_invoice_line = invoice_line
    >>> asset.value == Decimal('1000')
    True
    >>> asset.start_date == supplier_invoice.invoice_date
    True
    >>> asset.end_date == (supplier_invoice.invoice_date +
    ...     relativedelta(years=2, days=-1))
    True
    >>> asset.quantity == 1
    True
    >>> asset.unit == unit
    True
    >>> asset.residual_value = Decimal('100')
    >>> asset.save()
    >>> Asset.create_lines([asset.id], config.context)
    >>> asset.reload()
    >>> len(asset.lines)
    24
    >>> [l.depreciation for l in asset.lines] == [Decimal('37.5')] * 24
    True
    >>> asset.lines[0].actual_value == Decimal('962.5')
    True
    >>> asset.lines[0].accumulated_depreciation == Decimal('37.5')
    True
    >>> asset.lines[11].actual_value == Decimal('550')
    True
    >>> asset.lines[11].accumulated_depreciation == Decimal('450')
    True
    >>> asset.lines[-1].actual_value == Decimal('100')
    True
    >>> asset.lines[-1].accumulated_depreciation == Decimal('900')
    True
    >>> Asset.run([asset.id], config.context)
    >>> asset.reload()

Create Moves for 3 months::

    >>> create_moves = Wizard('account.asset.create_moves')
    >>> create_moves.form.date = (supplier_invoice.invoice_date
    ...     + relativedelta(months=3))
    >>> create_moves.execute('create_moves')
    >>> (depreciation_account.debit, depreciation_account.credit) == \
    ...     (Decimal('0'), Decimal('112.5'))
    True
    >>> (expense.debit, expense.credit) == \
    ...     (Decimal('112.5'), Decimal('0'))
    True

Update the asset::

    >>> update = Wizard('account.asset.update', [asset])
    >>> update.form.value = Decimal('1100')
    >>> update.execute('update_asset')
    >>> update.form.amount == Decimal('100')
    True
    >>> update.execute('create_move')
    >>> asset.reload()
    >>> asset.value == Decimal('1100')
    True
    >>> [l.depreciation for l in asset.lines[:3]] == [Decimal('37.5')] * 3
    True
    >>> [l.depreciation for l in asset.lines[3:-1]] == [Decimal('42.26')] * 20
    True
    >>> asset.lines[-1].depreciation == Decimal('42.3')
    True
    >>> depreciation_account.reload()
    >>> (depreciation_account.debit, depreciation_account.credit) == \
    ...     (Decimal('100'), Decimal('112.5'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == (Decimal('112.5'), Decimal('100'))
    True

Create Moves for 3 other months::

    >>> create_moves = Wizard('account.asset.create_moves')
    >>> create_moves.form.date = (supplier_invoice.invoice_date
    ...     + relativedelta(months=6))
    >>> create_moves.execute('create_moves')
    >>> depreciation_account.reload()
    >>> (depreciation_account.debit, depreciation_account.credit) == \
    ...     (Decimal('100'), Decimal('239.28'))
    True
    >>> expense.reload()
    >>> (expense.debit, expense.credit) == \
    ...     (Decimal('239.28'), Decimal('100'))
    True

Sale the asset::

    >>> customer_invoice = Invoice(type='out_invoice')
    >>> customer_invoice.party = customer
    >>> invoice_line = InvoiceLine()
    >>> customer_invoice.lines.append(invoice_line)
    >>> invoice_line.product = asset_product
    >>> invoice_line.asset = asset
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('600')
    >>> invoice_line.account == revenue
    True
    >>> customer_invoice.save()
    >>> Invoice.post([customer_invoice.id], config.context)
    >>> customer_invoice.state
    u'posted'
    >>> asset.reload()
    >>> asset.customer_invoice_line == customer_invoice.lines[0]
    True
    >>> (revenue.debit, revenue.credit) == (Decimal('860.72'), Decimal('600'))
    True
    >>> asset_account.reload()
    >>> (asset_account.debit, asset_account.credit) == \
    ...     (Decimal('1000'), Decimal('1100'))
    True
    >>> depreciation_account.reload()
    >>> (depreciation_account.debit, depreciation_account.credit) == \
    ...     (Decimal('339.28'), Decimal('239.28'))
    True
