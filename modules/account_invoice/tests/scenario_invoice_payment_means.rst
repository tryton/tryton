==============================
Invoice Payment Means Scenario
==============================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertFalse

Activate modules::

    >>> config = activate_modules(
    ...     ['account_invoice', 'bank'], create_company, create_chart)

    >>> BankAccount = Model.get('bank.account')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> PaymentMeanRule = Model.get('account.invoice.payment.mean.rule')

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> customer = Party(name='Party')
    >>> customer.save()

Setup payment mean rules::

    >>> bank_account1 = BankAccount(owners=[Party(company.party.id)])
    >>> _ = bank_account1.numbers.new(type='other', number='12345')
    >>> bank_account1.save()

    >>> bank_account2 = BankAccount(owners=[Party(company.party.id)])
    >>> _ = bank_account1.numbers.new(type='other', number='67890')
    >>> bank_account2.save()

    >>> payment_mean_rule = PaymentMeanRule(instrument=bank_account1)
    >>> payment_mean_rule.save()

Create invoice without payment means::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> assertFalse(invoice.payment_means)
    >>> invoice.click('validate_invoice')
    >>> payment_mean, = invoice.payment_means
    >>> assertEqual(payment_mean.instrument, bank_account1)

Create invoice with payment means::

    >>> invoice = Invoice(type='out')
    >>> invoice.party = customer
    >>> payment_mean = invoice.payment_means.new()
    >>> payment_mean.instrument = bank_account2
    >>> invoice.click('post')
    >>> payment_mean, = invoice.payment_means
    >>> assertEqual(payment_mean.instrument, bank_account2)
