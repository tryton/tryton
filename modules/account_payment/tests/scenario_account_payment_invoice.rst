========================
Invoice Payment Scenario
========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment', 'account_invoice'], create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
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
    >>> payment.click('submit')

Check amount to pay::

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('80.00')

Process the payment::

    >>> process_payment = payment.click('process_wizard')

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
    >>> payment, = pay_line.actions[0]
    >>> payment.amount
    Decimal('100.00')
    >>> payment.amount = Decimal('30.00')
    >>> payment.save()
    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = pay_line.actions[0]
    >>> payment.amount
    Decimal('70.00')
    >>> payment.amount = Decimal('30.00')
    >>> payment.save()
    >>> payments = Payment.find([('state', '=', 'draft')])
    >>> Payment.click(payments, 'submit')

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
