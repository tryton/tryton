==============================
Invoice Payment Means Scenario
==============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertFalse

Activate modules::

    >>> config = activate_modules(
    ...     ['account_payment', 'account_invoice'], create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> PaymentJournal = Model.get('account.payment.journal')

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create payment journal::

    >>> payment_journal = PaymentJournal(name="Manual", process_method='manual')
    >>> payment_journal.save()

Create party::

    >>> customer = Party(name="Customer")
    >>> _ = customer.reception_direct_debits.new(journal=payment_journal)
    >>> customer.save()

Create invoice without payment means::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> assertFalse(invoice.payment_means)
    >>> invoice.click('validate_invoice')
    >>> payment_mean, = invoice.payment_means
    >>> assertEqual(payment_mean.instrument, customer.reception_direct_debits[0])

Create invoice with payment means::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> line = invoice.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10.0000')
    >>> payment_mean = invoice.payment_means.new()
    >>> payment_mean.instrument = customer.reception_direct_debits[0]
    >>> invoice.click('post')
    >>> payment_mean, = invoice.payment_means
    >>> assertEqual(payment_mean.instrument, customer.reception_direct_debits[0])

Try to pay with a different journal::

    >>> other_payment_journal, = payment_journal.duplicate()

    >>> line_to_pay, = invoice.lines_to_pay
    >>> pay_line = Wizard('account.move.line.pay', [line_to_pay])
    >>> pay_line.execute('next_')
    >>> pay_line.form.journal = other_payment_journal
    >>> pay_line.execute('next_')
    >>> payment, = pay_line.actions[0]
    >>> payment.click('submit')
    Traceback (most recent call last):
        ...
    PaymentMeanWarning: ...

Pay with the same journal::

    >>> payment.journal = payment_journal
    >>> payment.click('submit')
    >>> payment.state
    'submitted'
