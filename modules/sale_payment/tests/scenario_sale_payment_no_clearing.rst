=================================
Sale Payment Scenario No Clearing
=================================

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

    >>> config = activate_modules('sale_payment', create_company, create_chart)

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> Party = Model.get('party.party')
    >>> AccountConfiguration = Model.get('account.configuration')
    >>> Sale = Model.get('sale.sale')
    >>> Payment = Model.get('account.payment')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> payable = accounts['payable']

Create payment journal::

    >>> payment_journal = PaymentJournal(
    ...     name="Manual", process_method='manual')
    >>> payment_journal.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Default account product::

    >>> account_configuration = AccountConfiguration(1)
    >>> account_configuration.default_category_account_revenue = revenue
    >>> account_configuration.save()

Create a sale quotation::

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

Pay the sale using payment::

    >>> payment = Payment()
    >>> payment.journal = payment_journal
    >>> payment.kind = 'receivable'
    >>> payment.party = sale.party
    >>> payment.origin = sale
    >>> payment.amount = Decimal('100.00')
    >>> payment.click('submit')
    >>> payment.state
    'submitted'
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
    Decimal('0.00')
    >>> invoice.state
    'posted'
