=====================================
Supplier Credit Note Payment Scenario
=====================================

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

    >>> config = activate_modules(['account_payment', 'account_invoice'])

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> Payment = Model.get('account.payment')
    >>> PaymentJournal = Model.get('account.payment.journal')

Create company::

    >>> _ = create_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Create payment journal::

    >>> payment_journal = PaymentJournal(name="Manual", process_method='manual')
    >>> payment_journal.save()

Create party::

    >>> party = Party(name="Supplier")
    >>> party.save()

Create invoice::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> invoice.invoice_date = fiscalyear.start_date
    >>> line = invoice.lines.new()
    >>> line.account = accounts['expense']
    >>> line.quantity = -1
    >>> line.unit_price = Decimal('100')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'
    >>> invoice.amount_to_pay
    Decimal('-100.00')
    >>> line_to_pay, = invoice.lines_to_pay

Partially receive payment::

    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.execute('next_')
    >>> payment, = Payment.find()
    >>> payment.kind
    'receivable'
    >>> payment.amount = Decimal('20')
    >>> payment.click('submit')

Check amount to pay::

    >>> invoice.reload()
    >>> invoice.amount_to_pay
    Decimal('-80.00')
