========================
Invoice Payment Scenario
========================

Imports::
    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Activate modules::

    >>> config = activate_modules(['account_payment', 'account_invoice'])

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
    >>> payable = accounts['payable']
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']

    >>> Journal = Model.get('account.journal')
    >>> expense, = Journal.find([('code', '=', 'EXP')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual')
    >>> payment_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.description = 'Description'
    >>> line.account = revenue
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.amount_to_pay
    Decimal('100.00')
    >>> line_to_pay, = invoice.lines_to_pay
    >>> bool(line_to_pay.payment_direct_debit)
    False

Partially pay line::

    >>> Payment = Model.get('account.payment')
    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()
    >>> payment.amount = Decimal('20')
    >>> payment.click('approve')

Check amount to pay::

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('80.00')

Process the payment::

    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')

Check amount to pay::

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('80.00')

Fail the payment::

    >>> payment.click('fail')

Check amount to pay::

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('100.00')

Create multiple valid payments for one line::

    >>> line_to_pay, = invoice.lines_to_pay
    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payments = Payment.find([('state', '=', 'draft')])
    >>> for payment in payments:
    ...     payment.amount = Decimal('30')
    >>> Payment.click(payments, 'approve')

Check amount to pay::

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('40.00')

Set party as direct debit::

    >>> party.payment_direct_debit = True
    >>> party.save()

Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> bool(invoice.payment_direct_debit)
    True
    >>> line = invoice.lines.new()
    >>> line.description = 'Description'
    >>> line.account = revenue
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('50')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> line_to_pay, = invoice.lines_to_pay
    >>> bool(line_to_pay.payment_direct_debit)
    True
