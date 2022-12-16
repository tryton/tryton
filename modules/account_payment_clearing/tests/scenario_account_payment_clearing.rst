=========================
Payment Clearing Scenario
=========================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_payment_clearing::

    >>> Module = Model.get('ir.module')
    >>> account_payment_module, = Module.find(
    ...     [('name', '=', 'account_payment_clearing')])
    >>> account_payment_module.click('install')
    >>> account_statement_module, = Module.find(
    ...     [('name', '=', 'account_statement')])
    >>> account_statement_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

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
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']

    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(name='Bank Clearing', type=payable.type,
    ...     reconcile=True, deferral=True, parent=payable.parent, kind='other')
    >>> bank_clearing.save()

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
