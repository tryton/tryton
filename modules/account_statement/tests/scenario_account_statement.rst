==========================
Account Statement Scenario
==========================

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

Install account_statement and account_invoice::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...     ('name', 'in', ('account_statement', 'account_invoice')),
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
    >>> party = Party(name='B2CK')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
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
    >>> expense, = Account.find([
    ...     ('kind', '=', 'expense'),
    ...     ('company', '=', company.id),
    ... ])
    >>> cash, = Account.find([
    ...     ('name', '=', 'Main Cash'),
    ...     ('company', '=', company.id),
    ... ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create parties::

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

Create 2 customer invoices::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> customer_invoice1 = Invoice(type='out_invoice')
    >>> customer_invoice1.party = customer
    >>> customer_invoice1.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> customer_invoice1.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('100')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_invoice1.save()
    >>> Invoice.post([customer_invoice1.id], config.context)
    >>> customer_invoice1.state
    u'posted'

    >>> customer_invoice2 = Invoice(type='out_invoice')
    >>> customer_invoice2.party = customer
    >>> customer_invoice2.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> customer_invoice2.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('150')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_invoice2.save()
    >>> Invoice.post([customer_invoice2.id], config.context)
    >>> customer_invoice2.state
    u'posted'

Create 1 customer credit note::

    >>> customer_credit_note = Invoice(type='out_credit_note')
    >>> customer_credit_note.party = customer
    >>> customer_credit_note.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> customer_credit_note.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('50')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_credit_note.save()
    >>> Invoice.post([customer_credit_note.id], config.context)
    >>> customer_credit_note.state
    u'posted'

Create 1 supplier invoices::

    >>> supplier_invoice = Invoice(type='in_invoice')
    >>> supplier_invoice.party = supplier
    >>> supplier_invoice.payment_term = payment_term
    >>> invoice_line = InvoiceLine()
    >>> supplier_invoice.lines.append(invoice_line)
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('50')
    >>> invoice_line.account = expense
    >>> invoice_line.description = 'Test'
    >>> supplier_invoice.invoice_date = today
    >>> supplier_invoice.save()
    >>> Invoice.post([supplier_invoice.id], config.context)
    >>> supplier_invoice.state
    u'posted'

Create statement::

    >>> StatementJournal = Model.get('account.statement.journal')
    >>> Statement = Model.get('account.statement')
    >>> StatementLine = Model.get('account.statement.line')

    >>> sequence = Sequence(name='Satement',
    ...     code='account.journal',
    ...     company=company,
    ... )
    >>> sequence.save()
    >>> account_journal = AccountJournal(name='Statement',
    ...     type='statement',
    ...     credit_account=cash,
    ...     debit_account=cash,
    ...     sequence=sequence,
    ... )
    >>> account_journal.save()

    >>> statement_journal = StatementJournal(name='Test',
    ...     journal=account_journal,
    ... )
    >>> statement_journal.save()

    >>> statement = Statement(journal=statement_journal,
    ...     start_balance=Decimal('0'),
    ...     end_balance=Decimal('80'),
    ... )

Received 180 from customer::

    >>> statement_line = StatementLine()
    >>> statement.lines.append(statement_line)
    >>> statement_line.date = today
    >>> statement_line.amount = Decimal('180')
    >>> statement_line.party = customer
    >>> statement_line.account == receivable
    True
    >>> statement_line.invoice = customer_invoice1
    >>> statement_line.amount == Decimal('100')
    True
    >>> statement_line = statement.lines[-1]
    >>> statement_line.amount == Decimal('80')
    True
    >>> statement_line.party == customer
    True
    >>> statement_line.account == receivable
    True
    >>> statement_line.invoice = customer_invoice2
    >>> statement_line.amount == Decimal('80')
    True

Paid 50 to customer::

    >>> statement_line = StatementLine()
    >>> statement.lines.append(statement_line)
    >>> statement_line.date = today
    >>> statement_line.amount = Decimal('-50')
    >>> statement_line.party = customer
    >>> statement_line.account = receivable
    >>> statement_line.invoice = customer_credit_note

Paid 50 to supplier::

    >>> statement_line = StatementLine()
    >>> statement.lines.append(statement_line)
    >>> statement_line.date = today
    >>> statement_line.amount = Decimal('-60')
    >>> statement_line.party = supplier
    >>> statement_line.account == payable
    True
    >>> statement_line.invoice = supplier_invoice
    >>> statement_line.amount == Decimal('-50')
    True
    >>> statement_line = statement.lines.pop()
    >>> statement_line.amount == Decimal('-10')
    True

    >>> statement.save()

Validate statement::

    >>> Statement.validate_statement([statement.id], config.context)
    >>> statement.state
    u'validated'

Test invoice state::

    >>> customer_invoice1.reload()
    >>> customer_invoice1.state
    u'paid'
    >>> customer_invoice2.reload()
    >>> customer_invoice2.state
    u'posted'
    >>> customer_invoice2.amount_to_pay == Decimal('70')
    True
    >>> customer_credit_note.reload()
    >>> customer_credit_note.state
    u'paid'
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    u'paid'
