=========================
Payment Clearing Scenario
=========================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)
    >>> first = today  + relativedelta(day=1)

Install account_payment_clearing and account_statement::

    >>> config = activate_modules(['account_payment_clearing', 'account_statement'])

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
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']

    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(parent=payable.parent)
    >>> bank_clearing.name = 'Bank Clearing'
    >>> bank_clearing.type = payable.type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
    >>> bank_clearing.kind = 'other'
    >>> bank_clearing.save()

    >>> Journal = Model.get('account.journal')
    >>> expense, = Journal.find([('code', '=', 'EXP')])
    >>> revenue_journal, = Journal.find([('code', '=', 'REV')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual', clearing_journal=expense,
    ...     clearing_account=bank_clearing,
    ...     clearing_posting_delay=datetime.timedelta(1))
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

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
    >>> pay_line.execute('start')
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

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.form.date == today
    True
    >>> succeed.form.date = first
    >>> succeed.execute('succeed')
    >>> payment.state
    u'succeeded'
    >>> payment.clearing_move.date == first
    True
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
    >>> pay_line.execute('start')
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

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.execute('succeed')
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

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.form.date = yesterday
    >>> succeed.execute('succeed')
    >>> payment.state
    u'succeeded'

    >>> Cron = Model.get('ir.cron')
    >>> Company = Model.get('company.company')
    >>> cron_post_clearing_moves, = Cron.find([
    ...     ('model', '=', 'account.payment.journal'),
    ...     ('function', '=', 'cron_post_clearing_moves'),
    ...     ])
    >>> cron_post_clearing_moves.companies.append(Company(company.id))
    >>> cron_post_clearing_moves.click('run_once')

    >>> payment.reload()
    >>> clearing_move = payment.clearing_move
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

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.execute('succeed')
    >>> payment.state
    u'succeeded'

Create statement::

    >>> StatementJournal = Model.get('account.statement.journal')
    >>> Statement = Model.get('account.statement')
    >>> Sequence = Model.get('ir.sequence')

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

Create a statement that reimburse the payment group::

    >>> statement = Statement(name='test',
    ...     journal=statement_journal,
    ...     start_balance=Decimal('-50.00'),
    ...     end_balance=Decimal('0.00'),
    ...     )
    >>> line = statement.lines.new(date=today)
    >>> line.payment_group = payment.group
    >>> line.account == bank_clearing
    True
    >>> line.amount = Decimal('50.00')

    >>> statement.click('validate_statement')
    >>> statement.state
    u'validated'

Payment must be failed::

    >>> payment.reload()
    >>> payment.state
    u'failed'


Payment in a foreign currency
-----------------------------

Create a payment journal in Euro::

    >>> euro = get_currency('EUR')
    >>> euro_payment_journal = PaymentJournal(
    ...     name='Euro Payments', process_method='manual', currency=euro,
    ...     clearing_journal=expense, clearing_account=bank_clearing)
    >>> euro_payment_journal.save()

Create a payable move::

    >>> move = Move()
    >>> move.journal = expense
    >>> line = move.lines.new(
    ...     account=payable, party=supplier, credit=Decimal('20.00'),
    ...     amount_second_currency=Decimal('-40.00'), second_currency=euro)
    >>> line = move.lines.new(
    ...     account=expense, debit=Decimal('20.00'),
    ...     amount_second_currency=Decimal('40.00'), second_currency=euro)
    >>> move.click('post')

Pay the line::

    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = euro_payment_journal
    >>> pay_line.execute('start')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('40.00')
    >>> payment.click('approve')
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Succeed payment::

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.execute('succeed')
    >>> debit_line, = [l for l in payment.clearing_move.lines if l.debit > 0]
    >>> debit_line.debit
    Decimal('20.00')
    >>> debit_line.amount_second_currency
    Decimal('40.00')

Create receivable move::

    >>> move = Move()
    >>> move.journal = revenue_journal
    >>> line = move.lines.new(account=receivable, party=customer,
    ...     debit=Decimal('50.00'), second_currency=euro,
    ...     amount_second_currency=Decimal('100.0'))
    >>> line = move.lines.new(account=revenue, credit=Decimal('50.00'))
    >>> move.click('post')
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('50.00')

Pay the line::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = euro_payment_journal
    >>> pay_line.execute('start')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('100.0')
    >>> payment.click('approve')
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Succeed payment::

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.execute('succeed')
    >>> credit_line, = [l for l in payment.clearing_move.lines if l.credit > 0]
    >>> credit_line.credit
    Decimal('50.00')
    >>> credit_line.amount_second_currency
    Decimal('-100.0')

Validate Statement with processing payment
--------------------------------------------

Create a payable move::

    >>> move = Move()
    >>> move.journal = expense
    >>> line = move.lines.new(account=payable, party=supplier,
    ...     credit=Decimal('50.00'))
    >>> line = move.lines.new(account=expense, debit=Decimal('50.00'))
    >>> move.click('post')

Create a processing payment for the move::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('start')
    >>> payment, = Payment.find([('line', '=', line.id)])
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Create statement for the payment::

    >>> statement = Statement(name='test',
    ...     journal=statement_journal,
    ...     start_balance=Decimal('0.00'),
    ...     end_balance=Decimal('-50.00'))
    >>> line = statement.lines.new(date=today)
    >>> line.payment = payment
    >>> line.party == supplier
    True
    >>> line.account == bank_clearing
    True
    >>> line.amount
    Decimal('-50.00')
    >>> statement.save()

Validate statement and check the payment is confirmed::

    >>> statement.click('validate_statement')
    >>> statement.state
    u'validated'
    >>> line, = statement.lines
    >>> move_line, = [l for l in line.move.lines
    ...     if l.account == bank_clearing]
    >>> bool(move_line.reconciliation)
    True
    >>> payment.reload()
    >>> payment.state
    u'succeeded'
    >>> debit_line, = [l for l in payment.clearing_move.lines if l.debit > 0]
    >>> debit_line.debit
    Decimal('50.00')
