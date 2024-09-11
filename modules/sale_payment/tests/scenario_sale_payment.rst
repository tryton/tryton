=====================
Sale Payment Scenario
=====================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     ['sale_payment', 'account_payment_clearing'],
    ...     create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> payable = accounts['payable']

    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(parent=payable.parent)
    >>> bank_clearing.name = 'Bank Clearing'
    >>> bank_clearing.type = payable.type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
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
    >>> customer = Party(name='Customer')
    >>> customer.save()

Default account product::

    >>> AccountConfiguration = Model.get('account.configuration')
    >>> account_configuration = AccountConfiguration(1)
    >>> account_configuration.default_category_account_revenue = revenue
    >>> account_configuration.save()

Create a sale quotation::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.description = "Test"
    >>> sale_line.quantity = 1.0
    >>> sale_line.unit_price = Decimal(100)
    >>> sale.click('quote')
    >>> sale.total_amount
    Decimal('100.00')
    >>> sale.state
    'quotation'

Create a partial payment::

    >>> Payment = Model.get('account.payment')
    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = sale.party
    >>> payment.origin = sale
    >>> payment.amount = Decimal('40.00')
    >>> payment.click('submit')
    >>> payment.state
    'submitted'

Attempt to put sale back to draft::

    >>> sale.click('draft')
    Traceback (most recent call last):
        ...
    AccessError: ...
    >>> sale.state
    'quotation'

Attempt to cancel sale::

    >>> sale.click('cancel')
    Traceback (most recent call last):
        ...
    AccessError: ...
    >>> sale.state
    'quotation'

Revert sale to draft after failed payment::

    >>> process_payment = payment.click('process_wizard')
    >>> payment.click('fail')
    >>> payment.state
    'failed'
    >>> sale.click('draft')
    >>> sale.state
    'draft'

Attempt to add a second payment to draft sale::

    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = sale.party
    >>> payment.origin = sale
    >>> payment.amount = Decimal('30.00')
    >>> payment.save()
    Traceback (most recent call last):
        ...
    DomainValidationError: ...

Cancel the sale::

    >>> sale.click('cancel')
    >>> sale.state
    'cancelled'

Attempt to add a second payment to the cancelled sale::

    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = sale.party
    >>> payment.origin = sale
    >>> payment.amount = Decimal('30.00')
    >>> payment.save()
    Traceback (most recent call last):
        ...
    DomainValidationError: ...

Revive the sale::

    >>> sale.click('draft')
    >>> sale.click('quote')
    >>> sale.state
    'quotation'

Change the first payment to succeed::

    >>> payment, = sale.payments
    >>> payment.click('succeed')
    >>> sale.state
    'quotation'

Create and process a final payment::

    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = sale.party
    >>> payment.origin = sale
    >>> payment.amount = Decimal('60.00')
    >>> payment.click('submit')
    >>> process_payment = payment.click('process_wizard')
    >>> payment.click('succeed')

The sale should be processing::

    >>> sale.reload()
    >>> sale.state
    'processing'

Post the invoice and check amount to pay::

    >>> sale.click('process')
    >>> invoice, = sale.invoices
    >>> invoice.total_amount
    Decimal('100.00')
    >>> invoice.click('post')
    >>> invoice.amount_to_pay
    Decimal('0')
    >>> invoice.state
    'paid'

Fail one payment and check invoice is no more paid::

    >>> payment.click('fail')
    >>> invoice.reload()
    >>> invoice.state
    'posted'
