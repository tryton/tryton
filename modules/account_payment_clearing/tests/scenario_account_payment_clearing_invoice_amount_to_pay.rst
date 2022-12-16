======================================
Payment Clearing Invoice Amount to Pay
======================================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)
    >>> first = today  + relativedelta(day=1)

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment_clearing', 'account_invoice'])

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
    >>> expense = accounts['expense']
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']

    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(parent=payable.parent)
    >>> bank_clearing.name = 'Bank Clearing'
    >>> bank_clearing.type = payable.type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
    >>> bank_clearing.save()

    >>> Journal = Model.get('account.journal')
    >>> expense_journal, = Journal.find([('code', '=', 'EXP')])
    >>> revenue_journal, = Journal.find([('code', '=', 'REV')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='No Clearing',
    ...     process_method='manual')
    >>> payment_journal.save()
    >>> clearing_journal = PaymentJournal(name='Clearing',
    ...     process_method='manual', clearing_journal=expense,
    ...     clearing_account=bank_clearing)
    >>> clearing_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create and pay an invoice without clearing::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> invoice.save()
    >>> invoice.click('post')
    >>> invoice.amount_to_pay
    Decimal('100.00')

    >>> paid_line, = [l for l in invoice.move.lines if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [paid_line])
    >>> pay_line.execute('next_')
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('next_')

    >>> Payment = Model.get('account.payment')
    >>> payment, = Payment.find()
    >>> payment.click('submit')
    >>> payment.state
    'submitted'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.execute('succeed')

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('0.00')

Create an invoice and pay it::

    >>> invoice1 = Invoice()
    >>> invoice1.party = customer
    >>> line = invoice1.lines.new()
    >>> line.account = revenue
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> invoice1.save()
    >>> invoice1.click('post')
    >>> invoice1.amount_to_pay
    Decimal('100.00')

    >>> paid_line, = [l for l in invoice1.move.lines if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [paid_line])
    >>> pay_line.execute('next_')
    >>> pay_line.form.journal = clearing_journal
    >>> pay_line.execute('next_')

    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.click('submit')
    >>> payment.state
    'submitted'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.execute('succeed')

    >>> invoice1.reload()
    >>> invoice1.amount_to_pay
    Decimal('0')

Unreconcile the payment line and check the amount to pay::

    >>> other_line, = [l for l in paid_line.reconciliation.lines
    ...     if l != paid_line]
    >>> unreconcile = Wizard('account.move.unreconcile_lines', [paid_line])
    >>> invoice1.reload()
    >>> invoice1.amount_to_pay
    Decimal('0.00')

Create a second invoice and reconcile its line to pay with the payment::

    >>> invoice2 = Invoice()
    >>> invoice2.party = customer
    >>> line = invoice2.lines.new()
    >>> line.account = revenue
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('100')
    >>> invoice2.save()
    >>> invoice2.click('post')

    >>> inv2_line, = [l for l in invoice2.move.lines if l.account == receivable]
    >>> reconcile = Wizard(
    ...     'account.move.reconcile_lines', [inv2_line, other_line])

    >>> invoice1.reload()
    >>> invoice1.amount_to_pay
    Decimal('100.00')
    >>> invoice2.reload()
    >>> invoice2.amount_to_pay
    Decimal('0')
