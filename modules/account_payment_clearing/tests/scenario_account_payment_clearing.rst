=========================
Payment Clearing Scenario
=========================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_payment_clearing::

    >>> Module = Model.get('ir.module.module')
    >>> account_payment_module, = Module.find(
    ...     [('name', '=', 'account_payment_clearing')])
    >>> account_payment_module.click('install')
    >>> account_statement_module, = Module.find(
    ...     [('name', '=', 'account_statement')])
    >>> account_statement_module.click('install')
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
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
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> cash, = Account.find([
    ...         ('name', '=', 'Main Cash'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> bank_clearing = Account(name='Bank Clearing', type=payable.type,
    ...     reconcile=True, deferral=True, parent=payable.parent, kind='other')
    >>> bank_clearing.save()
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')
    >>> Journal = Model.get('account.journal')
    >>> expense, = Journal.find([('code', '=', 'EXP')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual', clearing_journal=expense,
    ...     clearing_account=bank_clearing)
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create payable move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = expense
    >>> line = move.lines.new(account=payable, party=supplier,
    ...     credit=Decimal('50.00'))
    >>> line = move.lines.new(account=expense, debit=Decimal('50.00'))
    >>> move.click('post')
    >>> payable.reload()
    >>> payable.balance
    Decimal('-50.00')

Partially pay the line::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('pay')
    >>> payment, = Payment.find()
    >>> payment.amount = Decimal('30.0')
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Succeed payment::

    >>> payment.click('succeed')
    >>> payment.state
    u'succeeded'
    >>> payment.clearing_move.state
    u'draft'
    >>> payable.reload()
    >>> payable.balance
    Decimal('-20.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('-30.00')
    >>> payment.line.reconciliation

Fail payment::

    >>> payment.click('fail')
    >>> payment.state
    u'failed'
    >>> payment.clearing_move
    >>> payment.line.reconciliation
    >>> payable.reload()
    >>> payable.balance
    Decimal('-50.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('0.00')

Pay the line::

    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('pay')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('50.00')
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Succeed payment::

    >>> payment.click('succeed')
    >>> payment.state
    u'succeeded'
    >>> payment.clearing_move.state
    u'draft'
    >>> payable.reload()
    >>> payable.balance
    Decimal('0.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('-50.00')
    >>> bool(payment.line.reconciliation)
    True

Fail payment::

    >>> payment.click('fail')
    >>> payment.state
    u'failed'
    >>> payment.clearing_move
    >>> payment.line.reconciliation

Succeed payment and post clearing::

    >>> payment.click('succeed')
    >>> payment.state
    u'succeeded'
    >>> clearing_move = payment.clearing_move
    >>> clearing_move.click('post')
    >>> clearing_move.state
    u'posted'

Fail payment with posted clearing::

    >>> payment.click('fail')
    >>> payment.state
    u'failed'
    >>> payment.clearing_move
    >>> payment.line.reconciliation
    >>> clearing_move.reload()
    >>> line, = [l for l in clearing_move.lines
    ...     if l.account == payment.line.account]
    >>> bool(line.reconciliation)
    True

Succeed payment to use on statement::

    >>> payment.click('succeed')
    >>> payment.state
    u'succeeded'

Create statement::

    >>> StatementJournal = Model.get('account.statement.journal')
    >>> Statement = Model.get('account.statement')

    >>> sequence = Sequence(name='Satement',
    ...     code='account.journal',
    ...     company=company,
    ... )
    >>> sequence.save()
    >>> account_journal = Journal(name='Statement',
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

    >>> statement = Statement(name='test',
    ...     journal=statement_journal,
    ...     start_balance=Decimal('0.00'),
    ...     end_balance=Decimal('-50.00'),
    ... )

Create a line for the payment::

    >>> line = statement.lines.new(date=today)
    >>> line.payment = payment
    >>> line.party == supplier
    True
    >>> line.account == bank_clearing
    True
    >>> line.amount
    Decimal('-50.00')

Remove the party must remove payment::

    >>> line.party = None
    >>> line.payment

    >>> line.payment = payment

Change account must remove payment::

    >>> line.account = receivable
    >>> line.payment

    >>> line.account = None
    >>> line.payment = payment

Validate statement::

    >>> statement.click('validate_statement')
    >>> statement.state
    u'validated'
    >>> line, = statement.lines
    >>> move_line, = [l for l in line.move.lines
    ...     if l.account == bank_clearing]
    >>> bool(move_line.reconciliation)
    True
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('0.00')
